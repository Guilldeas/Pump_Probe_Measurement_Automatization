import time
import os
import sys
from ctypes import *

def get_device_list_by_type(lib, device_type=0):
    # Create a buffer for the device list (max size: 512 bytes)
    buffer_size = 512
    receiveBuffer = create_string_buffer(buffer_size)

    # Call TLI_GetDeviceListByTypeExt
    result = lib.TLI_GetDeviceListByTypeExt(receiveBuffer, buffer_size, device_type)
    if result != 0:
        raise Exception(f"TLI_GetDeviceListByTypeExt failed with error code: {result}")

    # Decode and parse the comma-separated serial numbers
    device_list = receiveBuffer.value.decode("utf-8").split(",")
    return device_list


# Error descriptions dictionary. These errors are documented on the "Thorlabs Kinesis C API" HTML at this folder
# the C functions controlling the stage will return a 0 if nothing went wrong or any of these numbers if something 
# failed, the corresponding descriptions are extracted through get_error_description()
error_descriptions = {
    0: "FT_OK - Success",
    1: "FTDI and Communication error: FT_InvalidHandle - The FTDI functions have not been initialized. ",
    2: "FTDI and Communication error: FT_DeviceNotFound - Device not found. Ensure TLI_BuildDeviceList has been called.",
    3: "FTDI and Communication error: FT_DeviceNotOpened - The Device must be opened before it can be accessed. See the appropriate Open function for your device.",
    4: "FTDI and Communication error: FT_IOError - An I/O Error has occured in the FTDI chip.",
    5: "FTDI and Communication error: FT_InsufficientResources - There are Insufficient resources to run this application.",
    6: "FTDI and Communication error: FT_InvalidParameter - An invalid parameter has been supplied to the device. ",
    7: "FTDI and Communication error: FT_DeviceNotPresent - The Device is no longer present. The device may have been disconnected since the last TLI_BuildDeviceList() call. ",
    8: "FTDI and Communication error: FT_IncorrectDevice - The device detected does not match that expected./term> ",
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

# Choose whether to see the precious troubleshooting messages
Troubleshooting = True

def get_error_description(code):
    return error_descriptions.get(code, f"Unknown error with code: {code}")



def main():
    

    if sys.version_info < (3, 8):
        os.chdir(r"C:\Program Files\Thorlabs\Kinesis")
    else:
        os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")

    lib: CDLL = cdll.LoadLibrary("Thorlabs.MotionControl.Benchtop.BrushlessMotor.dll")

    # Uncomment this line if you are using simulations
    # lib.TLI_InitializeSimulations()

    # Set constants, serial number for the BBD301 delay stage driver can be read when loading the Kinesis 
    # Software, channel number is 1 because the BBD301 can only support one delay stage (I think).
    serial_num = c_char_p(b"103391384")
    channel = 1


    # Use a try loop to catch exceptions when loading risky functions that might fail
    try:
        # Build device list
        result = lib.TLI_BuildDeviceList()
        time.sleep(1)

        # Each of the C functions will have an associated error raised in case
        # the return is non 0. The program will stop, throwing it to terminal in 
        # case any of their outputs correlate with an internal error
        if result != 0 and Troubleshooting:
            raise Exception(f"TLI_BuildDeviceList failed: {get_error_description(result)}")

        else:
            print("TLI_BuildDeviceList succeeded")

            # Look at the list of connected devices and actually check whether our particular stage is there
            if (Troubleshooting):

                # Get the list of all BBD301 devices (their device's ID is 103)
                device_list = get_device_list_by_type(lib, device_type=103)

                if "103391384" in device_list:
                    print(f"BBD301's serial number IS in list: {device_list}")
                else:
                    print(f"BBD301's serial number is NOT in list: {device_list}")

                '''
                result = lib.BMC_CheckConnection(serial_num)
                if result != 0 and Troubleshooting:
                    raise Exception(f"BMC_CheckConnection failed: {get_error_description(result)}")
                else:
                    print("")
                '''

            # Open the device
            result = lib.BMC_Open(serial_num)
            time.sleep(1)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_Open failed: {get_error_description(result)}")
            else:
                print("BMC_Open passed without raising errors")

            # Enable the motor channel
            result = lib.BMC_EnableChannel(serial_num, channel)
            time.sleep(1)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_EnableChannel failed: {get_error_description(result)}")
            else:
                print(f"BMC_EnableChannel passed without raising erros, enabled channel: {channel}")

            # Start polling
            result = lib.BMC_StartPolling(serial_num, c_int(200))
            time.sleep(3)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_StartPolling failed: {get_error_description(result)}")
            else:
                print("BMC_StartPolling passed without raising errors")


            # Clear messaging que so that we can listen to the device for it's "finished homing" message
            result = lib.BMC_ClearMessageQueue(serial_num, channel)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_ClearMessageQueue failed: {get_error_description(result)}")
            else:
                print("BMC_ClearMessageQueue passed without raising errors")

            # Home the stage
            result = lib.BMC_Home(serial_num, channel)
            time.sleep(1)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_Home failed: {get_error_description(result)}")
            print("BMC_Home passed without raising errors")

            # Wait until we receive a message signaling homing completion
            # NOTE for the user dev: About ctypes, whenever you pass a variable to a funciton in C
            # if you want the function to edit the variable you have to pass it the pointer to the variable.
            # Pinters don't exist in Python so that is what we are simulating when we pass byref(variable) in ctypes
            # we need to do this since we wan't to update the variable every time we run the while loop
            message_type = c_ushort()  # WORD
            message_id = c_ushort()    # WORD
            message_data = c_uint()    # DWORD
            while(message_type.value != 2 or message_id.value != 0):
                result = lib.BMC_WaitForMessage(serial_num, channel, 
                                                byref(message_type), byref(message_id), byref(message_data))
                '''
                if result != 0 and Troubleshooting:
                    raise Exception(f"BMC_WaitForMessage failed: {get_error_description(result)}")
                print("BMC_WaitForMessage passed without raising errors")
            '''

            # Close the device
            result = lib.BMC_Close(serial_num)
            time.sleep(1)
            if result != 0 and Troubleshooting:
                raise Exception(f"BMC_Close failed: {get_error_description(result)}")
            else:
                print("BMC_Close passed without raising errors")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
