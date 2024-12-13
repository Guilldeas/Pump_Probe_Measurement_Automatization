# TO DO list
# 
# · Make it so whenever you do a new experiment you can change parameters without homing
# · Give a time estimation before starting the experiment, allow user to change variables if they didn't like the time estimation
# · Make it so if an error is caught user can fix it and then continue code execution from where it was left
#  




import time
import numpy as np
import os
import sys
from ctypes import *
from srsinst.sr860 import SR860
import pyvisa as visa 
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import argparse



Troubleshooting = False

def get_device_list_by_type(lib, device_type=0):
    # Create a buffer for the device list (max size: 512 bytes)
    buffer_size = 512
    receiveBuffer = create_string_buffer(buffer_size)

    # Call TLI_GetDeviceListByTypeExt
    result = lib.TLI_GetDeviceListByTypeExt(receiveBuffer, buffer_size, device_type)
    if result != 0:
        print(f"     Unable to connect to Delay Stage")
        raise Exception(f"     TLI_GetDeviceListByTypeExt failed with error code: {result}")
    elif Troubleshooting:
            print(f"     TLI_GetDeviceListByTypeExt passed without raising errors")

    # Decode and parse the comma-separated serial numbers
    device_list = receiveBuffer.value.decode("utf-8").split(",")
    return device_list


# Error descriptions dictionary. These errors are documented on the "Thorlabs Kinesis C API" HTML at this folder
# the C functions controlling the stage will return a 0 if nothing went wrong or any of these numbers if something 
# failed, the corresponding descriptions are extracted through get_error_description()
error_descriptions = {
    0: "FT_OK - Success",
    1: "FTDI and Communication error: FT_InvalidHandle - The FTDI functions have not been initialized.\nNote: This error get's thrown down a lot for reasons unrelated to device initialization",
    2: "FTDI and Communication error: FT_DeviceNotFound - Device not found. Ensure TLI_BuildDeviceList has been called.",
    3: "FTDI and Communication error: FT_DeviceNotOpened - The Device must be opened before it can be accessed. See the appropriate Open function for your device.",
    4: "FTDI and Communication error: FT_IOError - An I/O Error has occured in the FTDI chip.",
    5: "FTDI and Communication error: FT_InsufficientResources - There are Insufficient resources to run this application.",
    6: "FTDI and Communication error: FT_InvalidParameter - An invalid parameter has been supplied to the device. ",
    7: "FTDI and Communication error: FT_DeviceNotPresent - The Device is no longer present. The device may have been disconnected since the last TLI_BuildDeviceList() call. ",
    8: "FTDI and Communication error: FT_IncorrectDevice - The device detected does not match that expected./term> ",
    16: "Device Library Error: FT_NoDLLLoaded - The library for this device could not be found",
    17: "Device Library Error: FT_NoFunctionsAvailable - No functions available for this device",
    18: "Device Library Error: FT_FunctionNotAvailable - The function is not available for this device",
    19: "Device Library Error: FT_BadFunctionPointer - Bad function pointer detected",
    20: "Device Library Error: FT_GenericFunctionFail - The function failed to complete succesfully",
    21: "Device Library Error: FT_SpecificFunctionFail - The function failed to complete succesfully",
    32: "General DLL control error: TL_ALREADY_OPEN - Attempt to open a device that was already open. ",
    33: "General DLL control error: TL_NO_RESPONSE - The device has stopped responding. ",
    34: "General DLL control error: TL_NOT_IMPLEMENTED - This function has not been implemented. ",
    35: "General DLL control error: TL_FAULT_REPORTED - The device has reported a fault. ",
    36: "General DLL control error: TL_INVALID_OPERATION - The function could not be completed at this time. ",
    40: "General DLL control error: TL_DISCONNECTING - The function could not be completed because the device is disconnected",
    41: "General DLL control error: TL_FIRMWARE_BUG - The firmware has thrown an error ",
    42: "General DLL control error: TL_INITIALIZATION_FAILURE - The device has failed to initialize ",
    43: "General DLL control error: TL_INVALID_CHANNEL - An Invalid channel address was supplied ",
    37: "Motor Specific Error: TL_UNHOMED - The device cannot perform this function until it has been Homed",
    38: "Motor Specific Error: TL_INVALID_POSITION - The function cannot be performed as it would result in an illegal position. ",
    39: "Motor Specific Error: TL_INVALID_VELOCITY_PARAMETER - An invalid velocity parameter was supplied. The velocity must be greater than zero. ",
    44: "Motor Specific Error: TL_CANNOT_HOME_DEVICE - This device does not support Homing. Check the Limit switch parameters are correct.",
    45: "Motor Specific Error: TL_JOG_CONTINOUS_MODE - An invalid jog mode was supplied for the jog function.",
    46: "Motor Specific Error: TL_NO_MOTOR_INFO - There is no Motor Parameters available to convert Real World Units. ",
    47: "Motor Specific Error: TL_CMD_TEMP_UNAVAILABLE - Command temporarily unavailable, Device may be busy."
}


def get_error_description(code):
    return error_descriptions.get(code, f"Unknown error with code: {code}")


def evaluate_status_bits(serial_num, channel, lib):
    # Dictionary of status bit descriptions with meaning for both 0 and 1 states
    status_bit_descriptions = {
        0x00000001: ("CW hardware limit switch: No contact", "CW hardware limit switch: Contact"),
        0x00000002: ("CCW hardware limit switch: No contact", "CCW hardware limit switch: Contact"),
        0x00000004: ("CW software limit switch: No contact", "CW software limit switch: Contact"),
        0x00000008: ("CCW software limit switch: No contact", "CCW software limit switch: Contact"),
        0x00000010: ("Motor shaft not moving clockwise", "Motor shaft moving clockwise"),
        0x00000020: ("Motor shaft not moving counterclockwise", "Motor shaft moving counterclockwise"),
        0x00000040: ("Shaft not jogging clockwise", "Shaft jogging clockwise"),
        0x00000080: ("Shaft not jogging counterclockwise", "Shaft jogging counterclockwise"),
        0x00000100: ("Motor not connected", "Motor connected"),
        0x00000200: ("Motor not homing", "Motor homing"),
        0x00000400: ("Motor not homed", "Motor homed"),
        0x00001000: ("Trajectory not within tracking window", "Trajectory within tracking window"),
        0x00002000: ("Axis not within settled window", "Axis within settled window"),
        0x00004000: ("Axis within position error limit", "Axis exceeds position error limit"),
        0x00008000: ("No position module instruction error", "Position module instruction error exists"),
        0x00010000: ("Interlock link present in motor connector", "Interlock link missing in motor connector"),
        0x00020000: ("No position module over temperature warning", "Position module over temperature warning"),
        0x00040000: ("No position module bus voltage fault", "Position module bus voltage fault"),
        0x00080000: ("No axis commutation error", "Axis commutation error"),
        0x01000000: ("Axis phase current below limit", "Axis phase current exceeded limit"),
        0x80000000: ("Channel disabled", "Channel enabled"),
        
    }

    # Create a ctype variable for the returned DWORD
    status_bits = c_uint()

    # Call the function and get the status bits
    status_bits.value = lib.BMC_GetStatusBits(serial_num, channel)

    # Print the raw status bits
    print(f"     Raw status bits: {bin(status_bits.value)}")

    # Iterate over each bitmask in the dictionary
    for bitmask, (description_0, description_1) in status_bit_descriptions.items():
        # Check if the specific bit is set or not
        if (status_bits.value & bitmask) == bitmask:
            print(f"{description_1}")  # Bit is set
        else:
            print(f"{description_0}")  # Bit is not set


def move_to_position(lib, serial_num, channel, position):

    # Set a new position in real units [mm]
    if Troubleshooting:
        print(f"     New position: {position}mm")

    # Convert to device units
    new_pos_real = c_double(position)  # in real units
    new_pos_dev = c_int()
    result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                                channel, 
                                                new_pos_real, 
                                                byref(new_pos_dev), 
                                                c_int(0)) # Pass int 0 on last input to choose distance units

    if result != 0:
        raise Exception(f"     BMC_GetDeviceUnitFromRealValue failed: {get_error_description(result)}")
    elif Troubleshooting:
            print(f"     BMC_GetDeviceUnitFromRealValue passed without raising errors")

    print(f"     Moving to: {new_pos_real.value} [mm]")
    if Troubleshooting:
        print(f"     That position in device units is: {new_pos_dev.value} [dev units]")

    # Clear messaging que so that we can listen to the device for it's "finished moving" message
    result = lib.BMC_ClearMessageQueue(serial_num, channel)
    if result != 0:
        raise Exception(f"     BMC_ClearMessageQueue failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"     BMC_ClearMessageQueue passed without raising errors")

    # Feed the position now converted to device units to the device

    # This sleep function is sacred, society could collapse if you were to remove it
    time.sleep(1)
    result = lib.BMC_MoveToPosition(serial_num, channel, new_pos_dev)
    if result != 0:
        raise Exception(f"     BMC_MoveToPosition failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"     BMC_MoveToPosition passed without raising errors")    
    time.sleep(1)

    
    ########################### Wait for "finished moving" message ###########################

    # Wait until we receive message that movement has finished
    if Troubleshooting:
        print(f"     Awaiting stop moving message")
    # Reset variables (they are on a passing state from previous loop)
    message_type = c_ushort()  # WORD
    message_id = c_ushort()    # WORD
    message_data = c_uint()    # DWORD
    # Wait for "done moving" message
    while not (message_type.value == 2 and message_id.value == 1):
        result = lib.BMC_GetNextMessage(serial_num, channel, 
                                        byref(message_type), byref(message_id), byref(message_data))
        
    

    ########################### Read final position ###########################

    # Ask the device to evaluate it's current position 
    # (both polling and this funciton will suppousedly prompt the device to evaluate it)
    result = lib.BMC_RequestPosition(serial_num, channel)
    if result != 0:
        raise Exception(f"     BMC_RequestPosition failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"     BMC_RequestPosition passed without raising errors")
    time.sleep(0.2)

    # Get the last known position from the device in "Device units"
    dev_pos = c_int(lib.BMC_GetPosition(serial_num, channel))
    if Troubleshooting:
        print(f"     Device position in dev units: {dev_pos.value}")

    # Convert position from device units to real units
    real_pos = c_double()
    lib.BMC_GetRealValueFromDeviceUnit(serial_num,
                                        channel,
                                    dev_pos,
                                    byref(real_pos),
                                    c_int(0))

    print(f'     Arrived at position: {real_pos.value}')

    return dev_pos



####################################### MAIN CODE #######################################

def main(start_position, end_position, step_size, Troubleshooting):

    print(f"Initializing\n")
    
    if sys.version_info < (3, 8):
        os.chdir(r"C:\Program Files\Thorlabs\Kinesis")
    else:
        os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")

    lib: CDLL = cdll.LoadLibrary("Thorlabs.MotionControl.Benchtop.BrushlessMotor.dll")

    # Uncomment this line if you are using simulations
    # lib.TLI_InitializeSimulations()

    # Set constants with appropiate C type so that we can later pass them appropiately to the C DLL funcitons, 
    # serial number for the BBD301 delay stage driver can be read when loading the Kinesis software, 
    # channel number is 1 because the BBD301 can only support one delay stage (I think).
    serial_num = c_char_p(b"103391384")
    channel = c_short(1)


    # Use a try loop to catch exceptions when loading risky functions that might fail
    try:
        print(f"Configuring delay stage:")
        ########################### Build device list ###########################
        result = lib.TLI_BuildDeviceList()
        time.sleep(1)

        # Each of the C functions will have an associated error raised in case
        # the return is non 0. The program will stop, throwing it to terminal in 
        # case any of their outputs correlate with an internal error
        if result != 0 and Troubleshooting:
            raise Exception(f"     TLI_BuildDeviceList failed: {get_error_description(result)}")

        else:
            # Look at the list of connected devices and actually check whether our particular stage is there
        
            # Get the list of all BBD301 devices (their device's ID is 103)
            device_list = get_device_list_by_type(lib, device_type=103)

            if "103391384" in device_list:
                print(f"    Succesfuly found delay stage in device list")

            else:
                print(f"       BBD301's serial number is NOT in list: {device_list}")
                print(f"    Troubleshooting tip:\nTry closing Kinesis Software if ti's open\nTry disconnecting and connecting USB cable")
                raise Exception(f"     delay stage with serial number {serial_num.value} not in device list")


            ########################### Open the device ###########################
            result = lib.BMC_Open(serial_num)
            time.sleep(1)
            if result != 0:
                raise Exception(f"     BMC_Open failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_Open passed without raising errors")
            
            print(f"    Succesfuly connected to Delay Stage")

            ########################### Load Settings ###########################
            # This step fixes a bug where the device doesn't know how to convert real units to device units 
            # and improperly represented it's own travel limits. I don't know what it does or why we need it,
            # the C API documentation is astonishingly lackluster to a degree that I've come to despise
            # however it's fixing the bug so it stays here. 
            result = lib.BMC_LoadSettings(serial_num, channel)

            # This time the function returns a 0 for error and no error code
            if  result == 0:
                raise Exception(f"     BMC_LoadSettings failed")
            elif Troubleshooting:
                print(f"    BMC_LoadSettings passed without raising errors")


            ########################### Enable the motor channel ###########################
            result = lib.BMC_EnableChannel(serial_num, channel)
            time.sleep(1)
            if result != 0:
                raise Exception(f"     BMC_EnableChannel failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"     BMC_EnableChannel passed without raising erros, enabled channel: {channel.value}")
            
            print(f"     Succesfuly enabled channel {channel.value}")


            ########################### Start polling ###########################
            result = lib.BMC_StartPolling(serial_num, c_int(200))
            time.sleep(3)
            if result != 0:
                raise Exception(f"     BMC_StartPolling failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_StartPolling passed without raising errors")


            ########################### Move ###########################
            # Question the device whether we need to home the motor before moving
            can_move_without_homing_flag = c_bool()
            result = lib.BMC_CanMoveWithoutHomingFirst(byref(can_move_without_homing_flag)) # byref(variable) is a C pointer to that variable
            if result != 0:
                raise Exception(f"     BMC_CanMoveWithoutHomingFirst failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_CanMoveWithoutHomingFirst passed without raising errors")
            
            # The funciton will return True when we can move without homing first
            if (not can_move_without_homing_flag.value): # variable.value is how we "cast" a C variable back to Python

                ########################### Home first ###########################
                print(f"    Delay stage needs to be homed before moving")
                
                # Clear messaging que so that we can listen to the device for it's "finished homing" message
                result = lib.BMC_ClearMessageQueue(serial_num, channel)
                if result != 0:
                    raise Exception(f"     BMC_ClearMessageQueue failed: {get_error_description(result)}")
                elif Troubleshooting:
                    print(f"    BMC_ClearMessageQueue passed without raising errors")

                # Home the stage
                result = lib.BMC_Home(serial_num, channel)
                time.sleep(1)
                if result != 0:
                    raise Exception(f"     BMC_Home failed: {get_error_description(result)}")
                elif Troubleshooting:
                    print(f"    BMC_Home passed without raising errors")
                print(f"    Homing now")

                # Wait until we receive a message signaling homing completion
                message_type = c_ushort()  # WORD
                message_id = c_ushort()    # WORD
                message_data = c_uint()    # DWORD
                while not (message_type.value == 2 and message_id.value == 0):
                    result = lib.BMC_GetNextMessage(serial_num, channel, 
                                                    byref(message_type), byref(message_id), byref(message_data))
                
                print(f"    Finished homing delay stage")

            else:
                print(f"    Device doesn't need homing")

            ########################### Change velocity parameters ###########################
            # We set the parameters to the default that we see on screen when switching on the machine
            # We do this because Thorlabs engineers sell a 11K€ machine with some piece of sh*t software that
            # will immediately shoot your stage into over limit speeds when you run their github example with it
            # The machine will catch this self destruction attempt and stop itself abruptly (without throwing any
            # errors mind you). So we need to manually input some safe parameters when loading.
            # Don't trust their repo, don't trust their C_API docs, verify anything and everything these lazy engineers do            
            acceleration_real = c_double(900.0) # in mm/s^2
            max_velocity_real = c_double(45.0) # in mm/s 

            # We convert them to device units
            acceleration_dev = c_int()
            max_velocity_dev = c_int()
            result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                                        channel, 
                                                        max_velocity_real, 
                                                        byref(max_velocity_dev), 
                                                        c_int(1)) # Pass int 1 to convert to device velocity units
            if result != 0:
                raise Exception(f"     BMC_GetDeviceUnitFromRealValue failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_GetDeviceUnitFromRealValue passed without raising errors")

            result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                            channel, 
                                            acceleration_real, 
                                            byref(acceleration_dev), 
                                            c_int(2)) # Pass int 2 to convert to device acceleration units
            if result != 0:
                raise Exception(f"     BMC_GetDeviceUnitFromRealValue failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_GetDeviceUnitFromRealValue passed without raising errors")                                

            result = lib.BMC_SetVelParams(serial_num, channel, acceleration_dev, max_velocity_dev)
            if result != 0:
                raise Exception(f"     BMC_SetVelParams failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_SetVelParams passed without raising errors")

            if Troubleshooting:
                print(f"       Set max velocity param to {max_velocity_real.value}mm/s or {max_velocity_dev.value}dev units/s")
                print(f"       Set acceleration param to {acceleration_real.value}mm/s^2 or {acceleration_dev.value}dev units/s^2")
                print(f"    Checking velocity params")
            acceleration_dev = c_int()
            max_velocity_dev = c_int()
            result = lib.BMC_GetVelParams(serial_num, channel, byref(acceleration_dev),  byref(max_velocity_dev))
            if result != 0:
                raise Exception(f"     BMC_GetVelParams failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"    BMC_GetVelParams passed without raising errors")

            # Convert to real units
            max_velocity_real = c_double()
            lib.BMC_GetRealValueFromDeviceUnit(serial_num,
                                                channel,
                                                c_int(int(max_velocity_dev.value)), # Cast from long type to int type
                                                byref(max_velocity_real),
                                                c_int(1)) # Pass 1 for velocity
            
            acceleration_real = c_double()
            lib.BMC_GetRealValueFromDeviceUnit(serial_num,
                                                channel,
                                                c_int(int(acceleration_dev.value)),
                                                byref(acceleration_real),
                                                c_int(2)) # Pass 2 for acceleration
            print(f"       Succesfuly set stage's max velocity to {max_velocity_real.value}mm/s")
            print(f"       Succesfuly set stage's acceleration to {acceleration_real.value}mm/s^2")
            
            print(f"    Delay Stage is configured and ready\n")

            ########################### Establish lockin connection ###########################
            
            print(f"Configuring Lockin Amplifier:")
            print(f"    Attempting to connect to Lockin Amplifer")
            lockin_USB_port = 'COM5'
            lockin = SR860()
            try:
                lockin.connect('serial', lockin_USB_port)

            except Exception as e:
                print(f"Error{e}\nTroubleshooting:\n    1) Try to disconnect and recconnect the lockin USB then retry\n    2) If the problem persists verify that lockin is connected at {lockin_USB_port} on Windows device manager, if not change to correct port")
            print(f"    Succesfuly connected to Lockin Amplifier\n")

            ########################### Perform experiment ###########################

            # Repeat experiments without homing again
            New_Experiment = True
            while (New_Experiment):
                print(f"Measurement starts now:")
                # Define scan parameters
                limit_position__start = 0
                limit_position_end = 600
                settling_time = 5*lockin.signal.time_constant


                # Create a list to store both positions to scan and rms voltages measured
                Positions = []
                Position_within_limtis = True

                # Edge case: First position is computed outside the loop
                new_position = start_position

                # Check that the new computed position is whithin stage travel limits
                if (start_position <= new_position <= end_position):
                    Positions.append(new_position)

                # Following positions will be computed on the loop
                while(Position_within_limtis):

                    new_position = new_position + step_size

                    # Check that the new computed position is whithin stage travel limits
                    if (start_position <= new_position <= end_position):
                        Positions.append(new_position)
                    
                    # If not within limits then we stop adding new steps
                    else:
                        Position_within_limtis = False

                        # Add end position if not in list already
                        if (new_position != end_position):
                            Positions.append(end_position)

                Data = np.zeros_like(np.array(Positions))

                # Scan each position
                for index in range(0, len(Positions)):

                    print(f"    Measurement at step: {index+1} of {len(Positions)}")
                    move_to_position(lib, serial_num, channel, position=Positions[index]) # Move
                    
                    print(f"    Awaiting for filter settling")
                    time.sleep(settling_time)                                             # Settle
                    
                    print(f"    Capturing data")
                    Data[index] = lockin.data.value['R']                                  # Capture
                    print("\n")

                print(f"    Experiment is finished\n")                


                ########################### Store and display data ###########################

                # Store data
                print(f"Storing data on CSV file")

                # Create a DataFrame with headers
                df = pd.DataFrame({
                    "Delay position (mm)": np.array(Positions),
                    "Voltage from PD (Vrms)": Data
                })

                # Create a title with a date for the CSV file
                # Get current date as a string
                date_string = datetime.now().strftime("%Hh_%Mmin_%dd_%mm_%Yy")
                CSV_file_title = "Experiment_" + date_string + ".csv"

                # Create a string storing relevant experiment data
                experiment_params = str(f"Lockin was configurated to\n  time constant: {lockin.signal.time_constant}s?, filter slope: {lockin.signal.filter_slope}dB/?, input range: {lockin.signal.voltage_input_range}V?")

                # Write the parameters and data to a CSV file
                with open(CSV_file_title, "w") as file:
                    file.write(f"# {experiment_params}\n")  # Add the parameters as a comment line
                    df.to_csv(file, index=False)

                print(f"Showing curve on screen, please close the graphs window to continue7")
                # Show data
                plt.plot(Positions, Data)
                plt.xlabel('Delay position (mm)')
                plt.ylabel('Measured PD voltage (Vrms)')
                #plt.legend()
                plt.show()

                # Request user to whether they want to perform a new experiment
                user_input = input("To perform a new experiment input: y\n To close the program input: n\n")
                if (user_input == "y"):
                    New_Experiment = True
                if (user_input == "n"):
                    New_Experiment = False


            ########################### Close the device ###########################
            lib.BMC_StopPolling(serial_num, channel) # Does not return error codes
            
            result = lib.BMC_Close(serial_num)
            time.sleep(1)
            if result != 0:
                raise Exception(f"BMC_Close failed: {get_error_description(result)}")
            elif Troubleshooting:
                print(f"BMC_Close passed without raising errors")
            
            print(f"Succesfully closed communications to Delay Stage")


    # If any exception was caught while running the code above the program stops and 
    # reports the error back to the user
    except Exception as e:
        print(e)


########################### Parse variables passed from terminal by user ###########################

if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Run the experiment with specified parameters.")

    # Add arguments for configuration variables
    parser.add_argument("--start_position", type=float, required=True, help="Set position to start scan from in mm (minimum is 0 maximum is 600)")
    parser.add_argument("--end_position", type=float, required=True, help="Set position to end scan at in mm (minimum is 0 maximum is 600)")
    parser.add_argument("--step_size", type=int, required=True, help="Set the step size in mm")
    parser.add_argument("--Troubleshooting", type=bool, default=False, help="Choose whether to get a step by step verification of the C_API functions that passed (default: False)")


    # Parse arguments from the command line
    args = parser.parse_args()

    # Pass the arguments to the experiment function
    main(args.start_position, args.end_position, args.step_size, args.Troubleshooting)

