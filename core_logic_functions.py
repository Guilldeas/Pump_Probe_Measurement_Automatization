import time
import numpy as np
from ctypes import *
import pyvisa as visa 
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from pymeasure.adapters import SerialAdapter
from math import sqrt, pow




Troubleshooting = False

def get_device_list_by_type(lib, device_type=0):
    # Create a buffer for the device list (max size: 512 bytes)
    buffer_size = 512
    receiveBuffer = create_string_buffer(buffer_size)

    # Call TLI_GetDeviceListByTypeExt
    result = lib.TLI_GetDeviceListByTypeExt(receiveBuffer, buffer_size, device_type)
    if result != 0:
        print(f"    · Unable to connect to Delay Stage")
        raise Exception(f"TLI_GetDeviceListByTypeExt failed with error code: {result}")
    elif Troubleshooting:
            print(f"    · TLI_GetDeviceListByTypeExt passed without raising errors")

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
    print(f"    · Raw status bits: {bin(status_bits.value)}")

    # Iterate over each bitmask in the dictionary
    for bitmask, (description_0, description_1) in status_bit_descriptions.items():
        # Check if the specific bit is set or not
        if (status_bits.value & bitmask) == bitmask:
            print(f"{description_1}")  # Bit is set
        else:
            print(f"{description_0}")  # Bit is not set


def move_to_position(lib, serial_num, channel, delay_ps):
    
    # Convert position from picoseconds to real units [mm]
    light_speed_vacuum = 299792458 # m/s
    refraction_index_air = 1.0003
    ps_to_mm = light_speed_vacuum / (refraction_index_air * (1E9))
    distance_mm = delay_ps * ps_to_mm

    # Since light moves back and forth through the delay stage 
    # the position the stage needs to travel to is only half the distance
    position = distance_mm / 2

    # Convert from real units to device units [steps]
    new_pos_real = c_double(position)  # in real units
    new_pos_dev = c_int()
    result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                                channel, 
                                                new_pos_real, 
                                                byref(new_pos_dev), 
                                                c_int(0)) # Pass int 0 on last input to choose distance units

    if result != 0:
        raise Exception(f"BMC_GetDeviceUnitFromRealValue failed: {get_error_description(result)}")
    elif Troubleshooting:
            print(f"    · BMC_GetDeviceUnitFromRealValue passed without raising errors")

    #print(f"    · Moving stage to position: {round(new_pos_real.value, 2)} [mm]")
    if Troubleshooting:
        print(f"    · That position in device units is: {new_pos_dev.value} [dev units]")

    # Clear messaging que so that we can listen to the device for it's "finished moving" message
    result = lib.BMC_ClearMessageQueue(serial_num, channel)
    if result != 0:
        raise Exception(f"BMC_ClearMessageQueue failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"    · BMC_ClearMessageQueue passed without raising errors")

    # Feed the position now converted to device units to the device

    # This sleep function is sacred, society could collapse if you were to remove it!!!
    time.sleep(1)
    result = lib.BMC_MoveToPosition(serial_num, channel, new_pos_dev)
    if result != 0:
        raise Exception(f"BMC_MoveToPosition failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"    · BMC_MoveToPosition passed without raising errors")    
    time.sleep(1)

    
    ########################### Wait for "finished moving" message ###########################

    # Wait until we receive message that movement has finished
    if Troubleshooting:
        print(f"    · Awaiting stop moving message")
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
        raise Exception(f"BMC_RequestPosition failed: {get_error_description(result)}")
    elif Troubleshooting:
        print(f"    · BMC_RequestPosition passed without raising errors")
    time.sleep(0.2)

    # Get the last known position from the device in "Device units"
    dev_pos = c_int(lib.BMC_GetPosition(serial_num, channel))
    if Troubleshooting:
        print(f"    · Device position in dev units: {dev_pos.value}")

    # Convert position from device units to real units
    real_pos = c_double()
    lib.BMC_GetRealValueFromDeviceUnit(serial_num,
                                        channel,
                                    dev_pos,
                                    byref(real_pos),
                                    c_int(0))

    # Convert back from mm to ps and report to user
    mm_to_ps = 1 / ps_to_mm
    #print(f'     Arrived at position: {round(real_pos.value * mm_to_ps, 2)}ps')

    # Return position at the end of movement in ps
    return real_pos.value * mm_to_ps



def is_valid_file_name(file_name):
    # Define invalid characters for Windows file names
    invalid_chars = '<>:"/\\|?*'
    # Reserved file names in Windows
    reserved_names = ["CON", "PRN", "AUX", "NUL"] + \
                     [f"COM{i}" for i in range(1, 10)] + \
                     [f"LPT{i}" for i in range(1, 10)]
    
    # Check for invalid characters
    for char in invalid_chars:
        if char in file_name:
            return False
    
    # Check for reserved names
    if file_name.upper() in reserved_names:
        return False
    
    # Check for trailing dots or spaces
    if file_name.endswith('.') or file_name.endswith(' '):
        return False
    
    # File name is valid
    return True


########################### Lockin Functions ###########################


# --- Initialize Connection ---
def initialize_connection(port="COM5", baudrate=115200, timeout=1):
    """
    Initializes the RS232 connection using PyMeasure's SerialAdapter.
    Returns the initialized adapter.
    """
    try:
        adapter = SerialAdapter(port=port, baudrate=baudrate, timeout=timeout)
        adapter.connection.reset_input_buffer()
        print(f"    ·RS232 communication initialized successfully")
        return adapter
    except Exception as e:
        raise Exception(f"Error initializing connection: {e}")
        return None



#------ Configure lockin sensitivity ------
def set_sensitivity(adapter, sensitivity):
    """
    Sets the SR860 sensitivity to the specified value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.
        sensitivity: float - Desired sensitivity value (e.g., 1.0, 500e-3).
    
    Raises:
        ValueError: If the provided sensitivity is not in the predefined list.
    """
    # Sensitivity levels mapped to their indices (from the SR860 manual)
    sensitivity_table = {
        0: 1.0,       1: 500e-3,  2: 200e-3,  3: 100e-3,  4: 50e-3,  5: 20e-3,
        6: 10e-3,     7: 5e-3,    8: 2e-3,    9: 1e-3,   10: 500e-6, 11: 200e-6,
        12: 100e-6,  13: 50e-6,  14: 20e-6,  15: 10e-6,  16: 5e-6,   17: 2e-6,
        18: 1e-6,    19: 500e-9, 20: 200e-9, 21: 100e-9, 22: 50e-9,  23: 20e-9,
        24: 10e-9,   25: 5e-9,   26: 2e-9,   27: 1e-9
    }

    # Find the index for the given sensitivity
    index = None
    for key, value in sensitivity_table.items():
        if abs(value - sensitivity) < 1e-12:  # Compare with tolerance for floats
            index = key
            break

    # If sensitivity not found, raise an error
    if index is None:
        raise ValueError(f"Error: Tried to set sensitivity to invalid value: {sensitivity} V. "
                         f"Valid sensitivities are: {list(sensitivity_table.values())}")

    # Send the SCAL command with the selected index
    try:
        command = f"SCAL {index}\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure the instrument processes the command
        print(f"    ·Sensitivity set to {sensitivity} V (Index {index}).")
    except Exception as e:
        raise Exception(f"Error setting sensitivity: {e}")


#------ Configure lockin time constant ------
def set_time_constant(adapter, time_constant):
    """
    Sets the SR860 time constant to the specified value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.
        time_constant: float - Desired time constant value in seconds (e.g., 1e-6 for 1 μs).
    
    Raises:
        ValueError: If the provided time constant is not in the predefined list.
    """
    # Time constant levels mapped to their indices (from the SR860 manual)
    time_constant_table = {
        0: 1e-6,    1: 3e-6,    2: 10e-6,   3: 30e-6,   4: 100e-6,  5: 300e-6,
        6: 1e-3,    7: 3e-3,    8: 10e-3,   9: 30e-3,   10: 100e-3, 11: 300e-3,
        12: 1,      13: 3,      14: 10,     15: 30,     16: 100,    17: 300,
        18: 1e3,    19: 3e3,    20: 10e3,   21: 30e3
    }

    # Find the index for the given time constant
    index = None
    for key, value in time_constant_table.items():
        if abs(value - time_constant) < 1e-12:  # Compare with tolerance for floats
            index = key
            break

    # If time constant not found, raise an error
    if index is None:
        raise ValueError(f"Error: Invalid time constant: {time_constant} s. "
                         f"Valid time constants are: {list(time_constant_table.values())}")

    # Send the OFLT command with the selected index
    try:
        command = f"OFLT {index}\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure the instrument processes the command
        print(f"    ·Time constant set to {time_constant} s (Index {index}).")
    except Exception as e:
        raise Exception(f"Error setting time constant: {e}")



#------ Configure lockin filter slope ------
def set_filter_slope(adapter, roll_off):
    """
    Sets the SR860 filter roll off to the specified value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.
        roll off: float - Desired roll off value in dB/oct
    
    Raises:
        ValueError: If the provided roll off is not in the predefined list.
    """
    # Time constant levels mapped to their indices (from the SR860 manual)
    filter_slope_table = {0:6, 1:12, 2:18, 3:24} # In dB/Oct

    # Find the index for the given filter slope
    index = None
    for key, value in filter_slope_table.items():
        if abs(value - roll_off) < 1e-12:  # Compare with tolerance for floats
            index = key
            break

    # If time constant not found, raise an error
    if index is None:
        raise ValueError(f"Error: Invalid filter slope: {roll_off} dB/oct. "
                         f"Valid filter slopes are: {list(filter_slope_table.values())}")

    # Send the OFSL command with the selected index
    try:
        command = f"OFSL {index}\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure the instrument processes the command
        print(f"    · Filter slope set to {roll_off} dB/oct.")
    except Exception as e:
        raise Exception(f"Error setting filter slope: {e}")



# --- Configure Lock-In Communication ---
def configure_lockin(adapter):
    """
    Configures and verifies the SR860 lock-in amplifier communication.
    Example: Clears status, verifies readiness.
    """
    try:
        #------ Clear status registers ------
        adapter.write("*CLS\n")  # Clear status registers
        time.sleep(0.1)
        print(f"    ·Lock-in amplifier status cleared.")


        #------ Check communication readiness ------
        adapter.write("*IDN?\n")  # Query instrument identification (optional for SR860)
        response = adapter.read().strip()
        if response:
            print(f"    ·Instrument ID: {response}")
        else:
            print("Warning: *IDN? command returned no response. Continuing anyway.")
        

        #------ Configure lockin to measure first harmonic ------
        adapter.write("HARM 1\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("HARM?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print(f"    ·Configured lockin to read 1st harmonic")
        else:
            print("Error: Unable to configure lockin to read 1st harmonic")


        #------ Configure lockin to external reference ------
        adapter.write("RSRC EXT\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("RSRC?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print(f"    ·Configured lockin to external reference")
        else:
            print("Error: Unable to configure lockin to external reference")


        #------ Configure lockin to external reference positive TTL ------
        adapter.write("RTRG POSttl\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("RTRG?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print(f"    ·Configured lockin to trigger reference at positive TTL")
        else:
            print("Error: Unable to configure lockin to trigger reference at positive TTL")


        #------ Configure lockin to external reference positive TTL ------
        # NOTE: What input impedance should we configure the reference to? 50 or 1Meg?
        # Lockin is configured to 50 Ohm but let's verify it on owners manual for chopper driver 
        adapter.write("REFZ 50\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("REFZ?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print(f"    ·Configured lockin to 50 Ohm input reference")
        else:
            print("Error: Unable to configure lockin to 50 Ohm input reference")


        #------ Configure lockin to read a voltage signal ------
        adapter.write("IVMD VOLTAGE\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("IVMD?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print(f"    ·Configured lockin to read input voltage")
        else:
            print("Error: Unable to configure lockin to read input voltage")


        #------ Configure lockin to read common voltage input ------
        adapter.write("ISRC A\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("ISRC?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print(f"    ·Configured lockin to read common voltage input")
        else:
            print("Error: Unable to configure lockin to read common voltage input")

        

        
    except Exception as e:
        raise Exception(f"Error configuring lock-in amplifier: {e}")



# --- Request signal strength ---
def request_signal_strength(adapter):
    """
    Requests the signal strength indicator which ranges from lowest (0) to overload (4).
    This indicator signifies how much of the ADCs headroom is filled. The input stage of the
    lockin consists on an amplifier that "scales up" the input voltage so that the ADC
    can read it better, however if we scale it up too much the amplifier may give the ADC
    a signal that is too high to read, we call this an "overload", however amplifying too 
    little is not good either since the input noise for the amplifier might be too significant
    compared to the signal level and SNR will suffer. We should always strive to read the highest
    signal level without saturating.
    """
    try:
        command = "ILVL?\n"  # queary signal level
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        return int(response.strip()) # between 0 (lowest) and 4 (overload)
    
    except Exception as e:
        raise Exception(f"Error requesting R: {e}")
        return None



# --- Request input amplifier range ---
def request_range(adapter):
    """
    Queries the SR860 for the current voltage input range and returns it as a human-readable value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.

    Returns:
        str: The voltage range (e.g., "1 V", "300 mV").
    """
    # Range indices mapped to their corresponding voltage ranges
    range_table = {
        0: "1 V",
        1: "300 mV",
        2: "100 mV",
        3: "30 mV",
        4: "10 mV"
    }

    try:
        # Query the current range with IRNG?
        command = "IRNG?\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure a response
        response = adapter.read().strip()

        # Convert the response to an integer index
        range_index = int(response)
        if range_index in range_table:
            return f"    ·Current Voltage Range: {range_table[range_index]}"
        else:
            return f"Error: Unexpected range index received: {range_index}"

    except Exception as e:
        raise Exception(f"Error requesting voltage range: {e}")
        return None



# --- Request R (Magnitude) ---
def request_R(adapter):
    """
    Requests the R value (magnitude) from the SR860.
    """
    try:
        command = "OUTP? 2\n"  # OUTP? 2 queries R
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        return float(response.strip()) # in Vrms
    
    except Exception as e:
        raise Exception(f"Error requesting R: {e}")
        return None



# --- Request AutoRange ---
def autorange(adapter):
    """
    Sends the command to enable autorange, this sets the input amplifiers gain to fit the signal
    level to the headroom on the subsequent ADC
    """
    try:
        command = "ARNG\n"  # Same result as pressing Auto Range on device
        adapter.write(command)
        time.sleep(0.1)
        '''
        # Always do it twice becuase in the case when the input signal is overloading the amplifier
        # the autorange function will set range to highest 1V, this might be too high for the signal
        # and thus we might loose some headroom 
        command = "ARNG\n"
        adapter.write(command)
        time.sleep(0.1)
        '''

    except Exception as e:
        raise Exception(f"Error sending AutoRange command: {e}")


# --- Request AutoScale ---
def autoscale(adapter):
    """
    Sends the command to autoscale. Scale is an artificial zoom done in postprocessing
    so it's generally just good enough to autorange for most measurements. Think of it
    like taking a picture, operating the focus would be like operating the range, zooming
    into the png once you are looking at the already snapped picture on your computer would
    be like adjusting autoscale, it should not add any real precission to the measurement, 
    however the manual advises that it should be properly set to calculate X noise and Y noise.
    I don't understand why but 'm doing it.
    """
    try:
        command = "ASCL\n"  # Same result as pressing Auto Scale on device
        adapter.write(command)
        time.sleep(0.1)


    except Exception as e:
        raise Exception(f"Error sending AutoScale command: {e}")



# --- Request Time Constant ---
def request_time_constant(adapter):
    """
    Queries the current time constant setting.
    """

    # List of time constants (in seconds) ordered such that their corresponding index correlates to the index returned by the OFLT? query 
    time_constants = [1E-6, 3E-6, 10E-6, 30E-6, 100E-6, 300E-6, 1E-3, 3E-3, 10E-3, 30E-3, 100E-3, 300E-3, 1, 3, 10, 30, 100, 300, 1E3, 3E3, 10E3, 30E3]

    try:
        command = "OFLT?\n"  # OFLT? queries the time constant index
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read()
        time_constant_index = int(response.strip())  # SR860 returns an index
        return time_constants[time_constant_index]
    
    except Exception as e:
        raise Exception(f"Error requesting time constant: {e}")
        return None



# --- Request Filter Slope ---
def request_filter_slope(adapter):
    """
    Queries the current filter slope setting.
    """
    filter_slopes = [6, 12, 18, 24] # In dB/Oct

    try:
        command = "OFSL?\n"  # OFSL? queries the filter slope index
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read()
        filter_slope_index = int(response.strip())  # SR860 returns an index
        return filter_slopes[filter_slope_index]
    
    except Exception as e:
        raise Exception(f"Error requesting filter slope: {e}")
        return None



# --- Request R noise ---
def request_R_noise(adapter):
    """
    Queries X noise and Y noise and calculates R noise from that.
    """


    try:
        command = "OUTP? XNOise\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        X_noise = float(response.strip()) # in Vrms

        command = "OUTP? YNOise\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        Y_noise = float(response.strip()) # in Vrms

        # If X noise and Y noise are Vrms values then 
        # we compute the addition of both like so
        R_noise = sqrt( pow(X_noise, 2) + pow(Y_noise, 2) )

        return R_noise
    
    except Exception as e:
        raise Exception(f"Error requesting R: {e}")
        return None



def find_next_sensitivity(adapter):
    """
    Finds and returns the sensitivity value that is right above the current input range.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.

    Returns:
        float: The next sensitivity value.
    """
    # Input range table (from the IRNG command)
    input_range_table = {
        0: "1 V",
        1: "300 mV",
        2: "100 mV",
        3: "30 mV",
        4: "10 mV"
    }

    # Sensitivity table (from the SCAL command)
    sensitivity_table = {
        0: 1.0,       1: 500e-3,  2: 200e-3,  3: 100e-3,  4: 50e-3,  5: 20e-3,
        6: 10e-3,     7: 5e-3,    8: 2e-3,    9: 1e-3,   10: 500e-6, 11: 200e-6,
        12: 100e-6,  13: 50e-6,  14: 20e-6,  15: 10e-6,  16: 5e-6,   17: 2e-6,
        18: 1e-6,    19: 500e-9, 20: 200e-9, 21: 100e-9, 22: 50e-9,  23: 20e-9,
        24: 10e-9,   25: 5e-9,   26: 2e-9,   27: 1e-9
    }

    try:
        # Step 1: Query the current input range
        command = "IRNG?\n"
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read().strip()

        current_range_index = int(response)
        if current_range_index not in input_range_table:
            print("Unexpected range index received. Aborting.")
            return None

        current_range = input_range_table[current_range_index]
        #print(f"    ·Current Input Range: {current_range} (Index {current_range_index})")

        # Step 2: Find the sensitivity above the current range
        range_voltage_map = {
            "1 V": 1.0,
            "300 mV": 300e-3,
            "100 mV": 100e-3,
            "30 mV": 30e-3,
            "10 mV": 10e-3
        }

        # Get the voltage of the current range
        current_range_value = range_voltage_map[current_range]

        # Find the first sensitivity greater than the current range value
        next_sensitivity = None
        for sensitivity in sorted(sensitivity_table.values()):
            if sensitivity > current_range_value:
                next_sensitivity = sensitivity
                break

        if next_sensitivity:
            #print(f"    ·Next Sensitivity: {next_sensitivity} V")
            return next_sensitivity
        else:
            #print("No sensitivity found above the current input range.")
            return max(range_voltage_map.values())

    except Exception as e:
        raise Exception(f"Error finding next sensitivity: {e}")
        return None



# --- Close Connection ---
def close_connection(adapter):
    """
    Closes the RS232 connection.
    """
    if adapter and adapter.connection.is_open:
        adapter.connection.close()
        print(f"    ·Serial port closed successfully.")