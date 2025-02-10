# TO DO list
# 
# · Check LP settling time (depends on filter slope too)
# · work in ps
# · Store data on neat dedicated folders (exclude them from git)
# · Make it so if an error is caught user can fix it and then continue code execution from where it was left
# · Verify whether reference input impedance is 50 or 1Meg 
#  




import time
import numpy as np
import os
import sys
from ctypes import *
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from math import ceil
import json
import core_logic_functions as clfun



# REMOVE LATER!
# Dummy functios to test development on machines that are not connected to experiment devices
def initialization_dummy(Troubleshooting):
    print("Start initializaiton")
    for task in range(1, 6):
        time.sleep(1)
        print(f"Task {task} completed")


def perform_experiment_dummy(Troubleshooting):
    print("Start Experiment")
    for task in range(1, 6):
        time.sleep(1)
        print(f"Task {task} completed")



####################################### MAIN CODE #######################################
def initialization(Troubleshooting):

    print(f"Please wait for initial setup\n")
    
    try:
        if sys.version_info < (3, 8):
            os.chdir(r"C:\Program Files\Thorlabs\Kinesis")
        else:
            os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")
    except Exception as e:
        print(f"Error while loading Thorlabs' Kinesis lirbary: {e}")
        print("Have you installed the Kinesis sotware?")

    global lib 
    lib = cdll.LoadLibrary("Thorlabs.MotionControl.Benchtop.BrushlessMotor.dll")

    # Extract default configuration values for both devices from the configuration file
    with open('Utils\default_config.json', "r") as json_file:
        default_config = json.load(json_file)

    default_values_delay_stage = default_config["Delay Stage Default Config Params"]
    default_values_lockin = default_config["Lockin Default Config Params"]

    serial_num_str = default_values_delay_stage["SerialNumber"]
    channel_int = default_values_delay_stage["Channel"]

    # Set constants with appropiate C type so that we can later pass them appropiately to the C DLL funcitons, 
    # serial number for the BBD301 delay stage driver can be read when loading the Kinesis software, 
    # channel number is 1 because the BBD301 can only support one delay stage (I think).
    global serial_num
    serial_num = c_char_p(serial_num_str.encode('utf-8')) # We use encode to pass it as bytes
    global channel
    channel = c_short(channel_int)


    # Use a try loop to catch exceptions when loading risky functions that might fail
    try:
        print(f"Configuring delay stage:")
        ########################### Build device list ###########################
        result = lib.TLI_BuildDeviceList()
        time.sleep(1)

        # Each of the C functions will have an associated error raised in case
        # the return is non 0. The program will stop, throwing it to terminal in 
        # case any of their outputs correlate with an internal error
        if result != 0:
            raise Exception(f"    · TLI_BuildDeviceList failed: {clfun.get_error_description(result)}")
        elif Troubleshooting:
            print(f"    · TLI_BuildDeviceList passed without raising errors")
        
    except Exception as e:
        print(f"    ·Error while Building device list {e}") 



    # Look at the list of connected devices and actually check whether our particular stage is there

    # Get the list of all BBD301 devices (their device's ID is 103)
    device_list = clfun.get_device_list_by_type(lib, device_type=103)

    if "103391384" in device_list:
        print(f"    ·Succesfuly found delay stage in device list")

    else:
        print(f"    ·   BBD301's serial number is NOT in list: {device_list}")
        print(f"    ·Troubleshooting tip:\n    Try closing Kinesis Software if it's open\n    Try disconnecting and connecting USB cable")
        raise Exception(f"    · delay stage with serial number {serial_num.value} not in device list")


    ########################### Open the device ###########################
    result = lib.BMC_Open(serial_num)
    time.sleep(1)
    if result != 0:
        raise Exception(f"    · BMC_Open failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_Open passed without raising errors")
    
    print(f"    ·Succesfuly connected to Delay Stage")

    ########################### Load Settings ###########################
    # This step fixes a bug where the device doesn't know how to convert real units to device units 
    # and improperly represented it's own travel limits. I don't know what it does or why we need it,
    # the C API documentation is astonishingly lackluster to a degree that I've come to despise
    # however it's fixing the bug so it stays here. 
    result = lib.BMC_LoadSettings(serial_num, channel)

    # This time the function returns a 0 for error and no error code
    if  result == 0:
        raise Exception(f"    · BMC_LoadSettings failed")
    elif Troubleshooting:
        print(f"    ·BMC_LoadSettings passed without raising errors")


    ########################### Enable the motor channel ###########################
    result = lib.BMC_EnableChannel(serial_num, channel)
    time.sleep(1)
    if result != 0:
        raise Exception(f"    · BMC_EnableChannel failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    · BMC_EnableChannel passed without raising erros, enabled channel: {channel.value}")
    
    print(f"    · Succesfuly enabled channel {channel.value}")


    ########################### Start polling ###########################
    result = lib.BMC_StartPolling(serial_num, c_int(200))
    time.sleep(3)
    if result != 0:
        raise Exception(f"    · BMC_StartPolling failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_StartPolling passed without raising errors")


    ########################### Home ###########################
    # Question the device whether we need to home the motor before moving
    can_move_without_homing_flag = c_bool()
    result = lib.BMC_CanMoveWithoutHomingFirst(byref(can_move_without_homing_flag)) # byref(variable) is a C pointer to that variable
    if result != 0:
        raise Exception(f"    · BMC_CanMoveWithoutHomingFirst failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_CanMoveWithoutHomingFirst passed without raising errors")
    
    # The funciton will return True when we can move without homing first
    if (not can_move_without_homing_flag.value): # variable.value is how we "cast" a C variable back to Python

        print(f"    ·Delay stage needs to be homed before moving")
        
        # Clear messaging que so that we can listen to the device for it's "finished homing" message
        result = lib.BMC_ClearMessageQueue(serial_num, channel)
        if result != 0:
            raise Exception(f"    · BMC_ClearMessageQueue failed: {clfun.get_error_description(result)}")
        elif Troubleshooting:
            print(f"    ·BMC_ClearMessageQueue passed without raising errors")

        # Home the stage
        result = lib.BMC_Home(serial_num, channel)
        time.sleep(1)
        if result != 0:
            raise Exception(f"    · BMC_Home failed: {clfun.get_error_description(result)}")
        elif Troubleshooting:
            print(f"    ·BMC_Home passed without raising errors")
        print(f"    ·Homing now")

        # Wait until we receive a message signaling homing completion
        message_type = c_ushort()  # WORD
        message_id = c_ushort()    # WORD
        message_data = c_uint()    # DWORD
        while not (message_type.value == 2 and message_id.value == 0):
            result = lib.BMC_GetNextMessage(serial_num, channel, 
                                            byref(message_type), byref(message_id), byref(message_data))
        
        print(f"    ·Finished homing delay stage")

    else:
        print(f"    ·Device doesn't need homing")

    ########################### Change velocity parameters ###########################
    # We set the parameters to the default that we see on screen when switching on the machines driver.
    # We do this because Thorlabs engineers sell a 11K€ machine with some piece of sh*t software that
    # will immediately shoot your stage into over limit speeds when you run it with their github code.
    # The machine will catch this self destruction attempt and stop itself abruptly (without throwing any
    # errors mind you). So we need to manually input some safe parameters when loading.
    # Don't trust their repo, don't trust their C_API docs, verify anything and everything.           
    acceleration_real = c_double(default_values_delay_stage["Acceleration_mm_per_s2"]) # in mm/s^2
    max_velocity_real = c_double(default_values_delay_stage["MaxVelocity_mm_per_s"]) # in mm/s

    # We convert them to device units
    acceleration_dev = c_int()
    max_velocity_dev = c_int()
    result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                                channel, 
                                                max_velocity_real, 
                                                byref(max_velocity_dev), 
                                                c_int(1)) # Pass int 1 to convert to device velocity units
    
    if result != 0:
        raise Exception(f"    · BMC_GetDeviceUnitFromRealValue failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_GetDeviceUnitFromRealValue passed without raising errors")

    result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                    channel, 
                                    acceleration_real, 
                                    byref(acceleration_dev), 
                                    c_int(2)) # Pass int 2 to convert to device acceleration units
    if result != 0:
        raise Exception(f"    · BMC_GetDeviceUnitFromRealValue failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_GetDeviceUnitFromRealValue passed without raising errors")                                

    result = lib.BMC_SetVelParams(serial_num, channel, acceleration_dev, max_velocity_dev)
    if result != 0:
        raise Exception(f"    · BMC_SetVelParams failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_SetVelParams passed without raising errors")

    if Troubleshooting:
        print(f"    ·   Set max velocity param to {max_velocity_real.value}mm/s or {max_velocity_dev.value}dev units/s")
        print(f"    ·   Set acceleration param to {acceleration_real.value}mm/s^2 or {acceleration_dev.value}dev units/s^2")
        print(f"    ·Checking velocity params")
    acceleration_dev = c_int()
    max_velocity_dev = c_int()
    result = lib.BMC_GetVelParams(serial_num, channel, byref(acceleration_dev),  byref(max_velocity_dev))
    if result != 0:
        raise Exception(f"    · BMC_GetVelParams failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_GetVelParams passed without raising errors")

    # Sanity check: Request params to device, convert back to real units and report to user.
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
    print(f"    ·   Succesfuly set stage's max velocity to {max_velocity_real.value}mm/s")
    print(f"    ·   Succesfuly set stage's acceleration to {acceleration_real.value}mm/s^2")
    
    print(f"    ·Delay Stage is configured and ready\n")



    ########################### Establish lockin connection ###########################
    
    print(f"Configuring Lockin Amplifier:")
    print(f"    ·Attempting to connect to Lockin Amplifer")
    lockin_USB_port = default_values_lockin["USBPort"]
    baud_rate = default_values_lockin["BaudRate"]
    time_out = default_values_lockin["TimeoutSeconds"]
    global adapter
    try:
        adapter = clfun.initialize_connection(port=lockin_USB_port, baudrate=baud_rate, timeout=time_out)

    except Exception as e:
        print(f"Error{e}\nTroubleshooting:\n    1) Try to disconnect and recconnect the lockin USB then retry\n    2) If the problem persists verify that lockin is connected at {lockin_USB_port} on Windows device manager, if not change to correct port")
    print(f"    ·Succesfuly connected to Lockin Amplifier\n")

    print(f"    ·Configuring lockin amplifier")

    try:
        clfun.configure_lockin(adapter)  
    except Exception as e:
        print(f"    ·Error while configuring lockin amplifier {e}") 

    print("Inital setup finished.\n")



# Honestly it's so messy to write the function here but I can't get the scope of adapter
# to be accesible at the main script so I'll take the L
def request_time_constant(start_position, end_position, step_size):

    time_constant = clfun.request_time_constant(adapter)
    settling_time = 5 * time_constant
    average_step_duration_sec = 0.5 + settling_time
    num_steps = ceil( (end_position - start_position) / step_size )
    estimated_duration = int(average_step_duration_sec * num_steps )

    return estimated_duration

    
    

def perform_experiment(parameters_dict):

    # The input dict contains information for each leg of the trip
    time_constant = parameters_dict["time_constant"]

    # Prepare lockin for experiment
    clfun.autorange(adapter)
    clfun.set_sensitivity(adapter, clfun.find_next_sensitivity(adapter))
    clfun.set_time_constant(adapter, time_constant)
    settling_time = 5 * time_constant



    ########################### Build scan positions list ###########################

    # Create a list of positions where the delay stage will move through
    Positions = []

    # Add values to the list for every leg
    for leg_number, leg_parameters in parameters_dict["trip_legs"].items():

        # Extract scan parameters for each leg
        start_position = leg_parameters["start_position"]
        end_position = leg_parameters["end_position"]
        step_size = leg_parameters["step_size"]

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
                if (end_position not in Positions):
                    Positions.append(end_position)

    # We create an empty array to hold the captured data for each position
    Photodiode_data = np.zeros_like(np.array(Positions))   



    ########################### Scan and Measure at list of positions ###########################

    for index in range(0, len(Positions)):

        print(f"    ·Measurement at step: {index+1} of {len(Positions)}")
        clfun.move_to_position(lib, serial_num, channel, position_ps=Positions[index]) # Move
        
        print(f"    ·Awaiting for filter settling")
        time.sleep(settling_time)                                                   # Settle
        
        print(f"    ·Capturing data")
        Photodiode_data[index] = clfun.request_R(adapter)                                      # Capture
        print("\n")

    print(f"Experiment is finished\n")

    # We also create non empty arays holding the error bars for each axis
    print(f"Computing Errors\n")
    Photodiode_data_errors = np.zeros_like(np.array(Positions))
    Position_errors = np.zeros_like(np.array(Positions))

    # To find the positional error we'll need to convert position error from mm to ps
    light_speed_vacuum = 299792458 # m/s
    refraction_index_air = 1.0003
    mm_to_ps = (refraction_index_air * (1E9)) / light_speed_vacuum

    # According to the datasheet for the ODL600M delay stage used in this experiment the "absolute on 
    # axis error" is +/-12um, this is a lower limit for the actual error I would expect
    # since error (the way I understand it) accumulates for larger distances. Oh well... ThorLabs you
    # did it again you sly dog
    delay_stage_error = 12 * mm_to_ps
    for index in range(0, len(Position_errors)):
        Position_errors[index] = delay_stage_error

    # The manual calls for a proper scale to be set before taking Xnoise or Ynoise measurements
    clfun.autoscale(adapter)

    # The manual for the older version (SR830) also calls for use of longer time constants to 
    # obtain better readings, it's best to do it good once than taking readings throughout 
    # the measurement 
    clfun.set_time_constant(adapter, 100)

    # We take one PD noise measurement and append it to all previous measurements
    R_noise = clfun.request_R_noise(adapter)
    for index in range(0, len(Photodiode_data_errors)):
        Photodiode_data_errors[index] = R_noise

    ########################### Store and display data ###########################
    print("Saving Data")
    # Create a folder to store data into

    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Get the parent directory
    #parent_dir = os.path.dirname(current_dir)

    # Define the Output folder path
    #output_folder = os.path.join(parent_dir, "Output")
    output_folder = os.path.join(current_dir, "Output")

    # Create the Output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")

    print(f"Writting CSV file")

    # Create a DataFrame with headers
    df = pd.DataFrame({
        "Time (ps)": np.array(Positions),
        "Time absolute On-axis error [+/-ps]": Position_errors,
        "Voltage from PD (Vrms)": Photodiode_data,
        "PD error [placeholder]": Photodiode_data_errors
    })

    # Get current date as a string
    date_string = datetime.now().strftime("%Hh_%Mmin_%dd_%mm_%Yy")

    # Create a subfolder at Output to store the experiment data
    experiment_name = parameters_dict["experiment_name"]
    data_folder = os.path.join(output_folder, experiment_name)
    data_folder = os.path.join(data_folder, date_string)
    os.makedirs(data_folder)

    file_name = parameters_dict["experiment_name"] + ".csv"
    file_path = os.path.join(data_folder, file_name)

    # Create a string storing relevant experiment data
    experiment_params = str(f"Date: {date_string},Lockin was configurated to\n  time constant: {time_constant}s,Filter slope: {clfun.request_filter_slope(adapter)}dB/Oct,Input range: {clfun.request_range(adapter)}V")

    # Write the parameters and data to a CSV file

    # Add the parameters as a comment line
    with open(file_path, "w") as file:
        file.write(f"# {experiment_params}\n")  

    # Append the rest of the data to the csv
    df.to_csv(file_path, index=False, mode="a", lineterminator="\n")

    '''
    print(f"Showing curve on screen, please close the graphs window to continue")
    # Show data
    plt.plot(Positions, Data)
    plt.xlabel('Delay position (mm)')
    plt.ylabel('Measured PD voltage (Vrms)')
    #plt.legend()
    plt.show()
    '''



def close_devices(Troubleshooting):
    ########################### Close the device ###########################
    lib.BMC_StopPolling(serial_num, channel) # Does not return error codes
    
    result = lib.BMC_Close(serial_num)
    time.sleep(1)
    if result != 0:
        raise Exception(f"BMC_Close failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"BMC_Close passed without raising errors")
    
    print(f"Succesfully closed communications to Delay Stage")

    clfun.close_connection(adapter)
    print("Succesfully closed connection to lockin")
            
