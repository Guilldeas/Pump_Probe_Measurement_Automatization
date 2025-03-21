import time
import numpy as np
import os
import sys
from ctypes import *
import pandas as pd
from datetime import datetime
import json
import core_logic_functions as clfun


# Dummy functios to test development on machines that are not connected to experiment devices
def initialization_dummy(Troubleshooting):
    print("Start initializaiton")
    for task in range(1, 3):
        time.sleep(1)
        print(f"Task {task} completed")


def perform_experiment_dummy(Troubleshooting):
    print("Start Experiment")
    for task in range(1, 3):
        time.sleep(1)
        print(f"Scan {task} completed")




def average_scans(Completed_scans, new_data):
    # We want to measure a live average, that is we need to update 
    # each averaged point in a graph as new points come in, to do so
    # we use this function which averages multiple lists and deals
    # with problems where the last scan is incomplete and thus a smaller
    # length, to do so it splits the averaging like so:
    #  
    # We slice completed scans by the len of the uncompleted scan
    # [a_0, a_1| a_2, a_3, a_4, a_5]
    # [b_0, b_1| b_2, b_3, b_4, b_5]
    #
    # Current scan taking place that is incomplete
    # [c_0, c_1]
    #
    # average left slices: [a_0, a_1], [b_0, b_1], [c_0, c_1]
    # average right slices: [a_2, a_3, a_4, a_5], [b_2, b_3, b_4, b_5]]
    #
    # We splice left and right averages into a final average
    # [avg_0, avg_1, avg_2, avg_3, avg_4, avg_5]


    def average_equal_lists(scans_list):

        try:
            # Takes a list of equal sized lists and returns an 
            # averaged list

            # Cast lists to arrays for easier element wise addition
            scans_array_list = []
            for scan in scans_list:
                scans_array_list.append(np.array(scan))
            
            # Average all scan arrays in list by summing them
            averaged_scans = np.zeros_like(np.array(scans_array_list[0]))
            for scan in scans_array_list:
                averaged_scans += scan
            
            # And dividing by amount of arrays
            averaged_scans = averaged_scans / len(scans_array_list)
            
            return averaged_scans.tolist()
        
        except ValueError:
            print(f'An ERROR occured when adding something in the following list:\n{scans_array_list}')

            raise ValueError

    # Append new data to completed scans
    Scans_ls = Completed_scans.copy()
    Scans_ls.append(new_data)

    # Deal with edge case where there are not enough scans to average
    if len(Scans_ls) > 1:

        # Find whether our averaging needs to deal with incompleted scans
        # by checkin whether the last scan is smaller than the previous one  
        if len(Scans_ls[-1]) == len(Scans_ls[-2]):
            return average_equal_lists(Scans_ls)

        else:

            # Compile list of scans sliced to match the length of the 
            # uncompleted scan
            left_slices_list = []
            for scan in Scans_ls[:-1]:
                left_slices_list.append(scan[:len(Scans_ls[-1])])
            
            # Include uncomplete scan
            left_slices_list.append(Scans_ls[-1])
            
            # Compile a second list of the "leftover" right slices
            right_slices_list = []
            for scan in Scans_ls[:-1]:
                right_slices_list.append(scan[len(Scans_ls[-1]):])
            
            # Average each of the groups, now with matching length
            left_average = average_equal_lists(left_slices_list)
            right_average = average_equal_lists(right_slices_list)

            # Combine them into a final average
            return left_average + right_average

    # This return signals that there is no average to plot for only
    # one scan
    else:
        return None





# --- Request Settling Time ---
def request_settling_time(time_constant, filter_slope, verbose=False):
    """
    Queries the current filter slope setting and time constant 
    to calculate the settling time to achieve 99.9% after a step response
    according to table 1 in "Zurich Instruments – White Paper: Principles of 
    lock-in detection and the state of the art".
    """

    # Keys in this dict correspond to filter roll-off and values are 
    # the settling time in multiples of tau that one should wait to achieve
    # 99.9% precision after a step change in signal on the lockin input
    settling_time_tau_multiples = {"6":6.91, "12":9.23, "18":11.23, "24":13.06}

    settling_time_seconds = time_constant * settling_time_tau_multiples[str(filter_slope)]

    # Inform the user, use fomratting to write only 2 significant digits
    if verbose:
        print(f"Lockin has been configured to time constant {float('%2g'%time_constant)}s and filter roll-off {filter_slope}dB/oct")
        print(f"This calls for a settling time of {float('%2g'%settling_time_seconds)}s to settle to 99.9% after a step response")

    return settling_time_seconds


####################################### MAIN CODE #######################################
def initialization(Troubleshooting):

    print(f"Please wait for initial setup\n")
    
    
    try:
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        Kinesis_folder_path = os.path.join(current_dir, "Utils", "Kinesis")
        if sys.version_info < (3, 8):
            os.chdir(Kinesis_folder_path)
        else:
            os.add_dll_directory(Kinesis_folder_path)

    except Exception as e:

        raise Exception(f"Error while loading Thorlabs' Kinesis lirbary:\n{e}\nPlease verify that you have installed Kinesis Software and that it is located in softwares subfolder Utils")
    

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
            raise Exception(f"TLI_BuildDeviceList failed:\n{clfun.get_error_description(result)}")
        elif Troubleshooting:
            print(f"    · TLI_BuildDeviceList passed without raising errors")
        
    except Exception as e:
        raise Exception(f"Error while Building device list:\n{e}") 



    # Look at the list of connected devices and actually check whether our particular stage is there

    # Get the list of all BBD301 devices (their device's ID is 103)
    device_list = clfun.get_device_list_by_type(lib, device_type=103)

    if "103391384" in device_list:
        print(f"    ·Succesfuly found delay stage in device list")

    else:
        print(f"    ·   BBD301's serial number is NOT in list: {device_list}")
        print(f"    ·Troubleshooting tip:\n    Try closing Kinesis Software if it's open\n    Try disconnecting and connecting USB cable")
        raise Exception(f"Delay stage with serial number {serial_num.value} not in device list")


    ########################### Open the device ###########################
    result = lib.BMC_Open(serial_num)
    time.sleep(1)
    if result != 0:
        raise Exception(f"BMC_Open failed: {clfun.get_error_description(result)}")
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
        raise Exception(f"BMC_LoadSettings failed")
    elif Troubleshooting:
        print(f"    ·BMC_LoadSettings passed without raising errors")


    ########################### Enable the motor channel ###########################
    result = lib.BMC_EnableChannel(serial_num, channel)
    time.sleep(1)
    if result != 0:
        raise Exception(f"BMC_EnableChannel failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    · BMC_EnableChannel passed without raising erros, enabled channel: {channel.value}")
    
    print(f"    · Succesfuly enabled channel {channel.value}")


    ########################### Start polling ###########################
    result = lib.BMC_StartPolling(serial_num, c_int(200))
    time.sleep(3)
    if result != 0:
        raise Exception(f"BMC_StartPolling failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_StartPolling passed without raising errors")


    ########################### Home ###########################
    # Question the device whether we need to home the motor before moving
    can_move_without_homing_flag = c_bool()
    result = lib.BMC_CanMoveWithoutHomingFirst(byref(can_move_without_homing_flag)) # byref(variable) is a C pointer to that variable
    if result != 0:
        raise Exception(f"BMC_CanMoveWithoutHomingFirst failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_CanMoveWithoutHomingFirst passed without raising errors")
    
    # The funciton will return True when we can move without homing first
    if (not can_move_without_homing_flag.value): # variable.value is how we "cast" a C variable back to Python

        print(f"    ·Delay stage needs to be homed before moving")
        
        # Clear messaging que so that we can listen to the device for it's "finished homing" message
        result = lib.BMC_ClearMessageQueue(serial_num, channel)
        if result != 0:
            raise Exception(f"BMC_ClearMessageQueue failed: {clfun.get_error_description(result)}")
        elif Troubleshooting:
            print(f"    ·BMC_ClearMessageQueue passed without raising errors")

        # Home the stage
        result = lib.BMC_Home(serial_num, channel)
        time.sleep(1)
        if result != 0:
            raise Exception(f"BMC_Home failed: {clfun.get_error_description(result)}")
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
        raise Exception(f"BMC_GetDeviceUnitFromRealValue failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_GetDeviceUnitFromRealValue passed without raising errors")

    result = lib.BMC_GetDeviceUnitFromRealValue(serial_num,
                                    channel, 
                                    acceleration_real, 
                                    byref(acceleration_dev), 
                                    c_int(2)) # Pass int 2 to convert to device acceleration units
    if result != 0:
        raise Exception(f"BMC_GetDeviceUnitFromRealValue failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"    ·BMC_GetDeviceUnitFromRealValue passed without raising errors")                                

    result = lib.BMC_SetVelParams(serial_num, channel, acceleration_dev, max_velocity_dev)
    if result != 0:
        raise Exception(f"BMC_SetVelParams failed: {clfun.get_error_description(result)}")
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
        raise Exception(f"BMC_GetVelParams failed: {clfun.get_error_description(result)}")
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
        raise Exception(f"Error while connecting to lockin with clfun.initialize_connection()\n{e}\nTroubleshooting:\n    1) Try to disconnect and recconnect the lockin USB then retry\n    2) If the problem persists verify that lockin is connected at {lockin_USB_port} on Windows device manager, if not change to correct port")
    
    print(f"    ·Succesfuly connected to Lockin Amplifier\n")

    print(f"    ·Configuring lockin amplifier")

    try:
        clfun.configure_lockin(adapter)  
    except Exception as e:
        raise Exception(f"Error while configuring lockin amplifier {e}") 

    print("Inital setup finished.\n")

    
    
def perform_experiment(parameters_dict, experiment_data_queue, abort_queue, fig, scan, num_scans, error_measurement_type, autoranging_type, Scans):

    global adapter

    print("------------------------------------------")
    print(f"Scan number {scan}/{num_scans}")

    # The input dict contains information for each leg of the trip
    time_constant = parameters_dict["time_constant"]
    roll_off = parameters_dict["roll_off"]

    # Prepare lockin for experiment

    # Adjust preamplifier gain on the lockin, this ensures optimal signal resolution
    clfun.autorange(adapter)

    # This sets sensitivity one step above gain, the point of this is to prevent 
    # sensitivity from saturating the signal
    clfun.set_sensitivity(adapter, clfun.find_next_sensitivity(adapter))
    clfun.set_time_constant(adapter, time_constant)
    clfun.set_filter_slope(adapter, roll_off)

    settling_time = request_settling_time(time_constant, filter_slope=roll_off, verbose=True)



    ########################### Build scan positions list ###########################

    # Create a list of positions where the delay stage will move through
    Positions = []

    # Add values to the list for every leg
    for leg_number, leg_parameters in parameters_dict["trip_legs"].items():

        # Extract scan parameters for each leg
        start_position = leg_parameters["abs time start [ps]"]
        end_position = leg_parameters["abs time end [ps]"]
        step_size = leg_parameters["step [ps]"]

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


    # We create empty lists to hold the captured data and error values
    Photodiode_data = []
    Photodiode_data_errors = []
    Position_errors = []

    # Raise this flag if you want to profile how much each step in the scanning loop takes
    profiling = True
    if profiling:
        moving = []
        settling = []
        autoscaling = []
        autoranging = []
        capturing = []
        estimating = []
        total = []

    if error_measurement_type == "Once at the start":
                print(f"    ·Measuring error only at the start\n")
                Photodiode_data_error = clfun.request_R_noise(adapter)
    
    time_zero = parameters_dict["time_zero"]
    if autoranging_type == "Once at time zero":
                print(f"    ·Autoranging only once, at the highest expected signal\n")
                position_ps = clfun.move_to_position(lib, serial_num, channel, delay_ps=time_zero)
                clfun.set_sensitivity(adapter, clfun.find_next_sensitivity(adapter))
                clfun.autorange(adapter)

    ########################### Scan and Measure at list of positions ###########################
    for index in range(0, len(Positions)):
        
        # Evaluate whether the user has pressed the abort button on the GUI
        try:
            abort_experiment = abort_queue.get_nowait()
        
        # Throws an error when queue is empty
        except Exception as e:
            abort_experiment = False
        
        if abort_experiment:
            
            # Return an error code to let experiment_thread_logic() there is no data to store
            # and we should close the GUI
            return 1
        
        # Register the timestamp when the iteration starts
        if profiling:
            startup_timestamp = time.time()

        print(f"Measurement at step: {index+1} of {len(Positions)}")
        
        
        ### Moving stage
        position_ps = clfun.move_to_position(lib, serial_num, channel, delay_ps=Positions[index] + time_zero)
        print(f"    ·Delay set to {round(position_ps - time_zero, 2)}ps")

        # For every function ran in the loop we store how much time it takes to run it
        if profiling:
            moved_timestamp = time.time()
            moving.append(moved_timestamp - startup_timestamp)


        ### Awaiting for filter settling
        print(f"    ·Awaiting {settling_time}s for filter settling")
        time.sleep(settling_time)
        if profiling:
            settled_timestamp = time.time()
            settling.append(settled_timestamp - moved_timestamp)


        ### Capturing data
        print(f"    ·Capturing data")
        if autoranging_type == "At every point":
            clfun.set_sensitivity(adapter, clfun.find_next_sensitivity(adapter))
            if profiling:
                autoscaled_timestamp = time.time()
                autoscaling.append(autoscaled_timestamp - settled_timestamp)

            clfun.autorange(adapter)
            if profiling:
                autoranged_timestamp = time.time()
                autoranging.append(autoranged_timestamp - autoscaled_timestamp)
    
            if profiling:
                data_captured_timestamp = time.time()
                capturing.append(data_captured_timestamp - autoranged_timestamp)

        Photodiode_data.append(clfun.request_R(adapter))


        ### Measuring errors
        if error_measurement_type == "At every point":
            print(f"    ·Measuring error\n")
            Photodiode_data_errors.append(clfun.request_R_noise(adapter))
            if profiling:
                error_estimated_timestamp = time.time()
                estimating.append(error_estimated_timestamp - data_captured_timestamp)
        
        elif error_measurement_type == "Once at the start":
                Photodiode_data_errors.append(Photodiode_data_error)
        

        ### Rounding up total elapsed time
        if profiling:
            total_timestamp = time.time() - startup_timestamp
            total.append(total_timestamp)

        # After every data point acquisition we calculate the live average 
        # (do so only if there is something to average)
        live_average = None
        if scan > 0:
            live_average = average_scans(Completed_scans=Scans, new_data=Photodiode_data)

        # Send data through queue to the GUI script to draw it. Do it with copies or else
        # we'll pass references to the local lists "Photodiode_data" and the GUI will
        # be able to access them and attempt to draw from them, this leads to an error
        # where the error bar has not been calculated but the photodiode data has been
        # acquired leading to an incorrect size error when plotting.
        # Passing the scan number will allow perform_experiment() to signal monitor_experiment()
        # That a new curve needs to be drawn
        data_packet = {
                        "Photodiode data": Photodiode_data.copy(), 
                        "Photodiode data errors": Photodiode_data_errors.copy(),
                        "Positions": Positions.copy(),
                        "Scan number": scan,
                        "Live average": live_average,
                      }
        experiment_data_queue.put(data_packet)

    print(f"Experiment is finished\n")

    # Report to user the average percentage of total iteration time spent on each function
    if profiling:
        print(f"The average time and percentage spent on each step for every action taken was:")
        print(f'    ·Moving stage : {round((sum(moving)/len(moving)), 1)}s and {round( 100 * (sum(moving)/len(moving)) / (sum(total)/len(total)), 1)}% of total\n')
        print(f'    ·Settling filter : {round((sum(settling)/len(settling)), 1)}s and {round( 100 * (sum(settling)/len(settling)) / (sum(total)/len(total)), 1)}%\n')
    
        if error_measurement_type == "At every point":
            print(f'    ·Estimating error from lockin : {round((sum(estimating)/len(estimating)), 1)}s and {round( 100 * (sum(estimating)/len(estimating)) / (sum(total)/len(total)), 1)}%\n')

        if autoranging_type == "At every point":
            print(f'    ·Autoscaling lockin : {round((sum(autoscaling)/len(autoscaling)), 1)}s and {round( 100 * (sum(autoscaling)/len(autoscaling)) / (sum(total)/len(total)), 1)}%\n')
            print(f'    ·Autoranging lockin : {round((sum(autoranging)/len(autoranging)), 1)}s and {round( 100 * (sum(autoranging)/len(autoranging)) / (sum(total)/len(total)), 1)}%\n')
            print(f'    ·Capturing data : {round((sum(capturing)/len(capturing)), 1)}s and {round( 100 * (sum(capturing)/len(capturing)) / (sum(total)/len(total)), 1)}%\n')
        
    
    # To find the positional error we'll need to convert position error from mm to ps
    # According to the datasheet for the ODL600M delay stage used in this experiment the "absolute on 
    # axis error" is +/-12um, this is a lower limit for the actual error I would expect
    # since error (the way I understand it) accumulates for larger distances. Oh well... ThorLabs you
    # did it again you sly dog
    light_speed_vacuum = 299792458 # m/s
    refraction_index_air = 1.0003
    mm_to_ps = (refraction_index_air * (1E9)) / light_speed_vacuum
    delay_stage_error = 12E-3 * mm_to_ps
    for index in range(0, len(Positions)):
        Position_errors.append(delay_stage_error)


    ########################### Store and display data ###########################
    print("Saving Data")
    # Create a folder to store data into

    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Define the Output folder path
    output_folder = os.path.join(current_dir, "Output")

    # Create the Output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")

    print(f"Writting CSV file")

    # Note the type of measurement that we just took 
    # to label data accordingly
    signal_type = clfun.request_signal_type(adapter)
    signal_type_str = ""
    if signal_type == 0:
        signal_type_str = "[Vrms]"

    if signal_type == 1:
            signal_type_str = "[Arms]"

    # Create a DataFrame with headers
    # So sorry for this hack but it's my last day working here and it's 7pm
    if live_average is not None:
        if error_measurement_type == "At every point":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level st current scan" + signal_type_str: Photodiode_data,
                "Signal error " + signal_type_str: Photodiode_data_errors,
            })
        
        if error_measurement_type == "Once at the start":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level " + signal_type_str: Photodiode_data,
                "Signal error (at the start)" + signal_type_str: Photodiode_data_errors,
                "Average of previous scans" + signal_type_str: live_average
            })
        
        elif error_measurement_type == "Never":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level " + signal_type_str: Photodiode_data,
                "Average of previous scans" + signal_type_str: live_average
            })

    else:
        if error_measurement_type == "At every point":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level st current scan" + signal_type_str: Photodiode_data,
                "Signal error " + signal_type_str: Photodiode_data_errors,
            })
        
        if error_measurement_type == "Once at the start":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level " + signal_type_str: Photodiode_data,
                "Signal error (at the start)" + signal_type_str: Photodiode_data_errors
            })
        
        elif error_measurement_type == "Never":
            data_df = pd.DataFrame({
                "Absolute Time [ps]": Positions,
                "Time absolute On-axis error [+/-ps] (placeholder data)": Position_errors,
                "Signal level " + signal_type_str: Photodiode_data,
            })

    # Get current date as a string
    date_string = datetime.now().strftime("%Hh_%Mmin_%dd_%mm_%Yy")

    # Create a subfolder at Output to store the experiment data
    experiment_name = parameters_dict["experiment_name"]
    data_folder = os.path.join(output_folder, experiment_name)
    data_folder = os.path.join(data_folder, str("scan_number_" + str(scan)))
    
    # Only create the data folder if it does not exist
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)

    file_name = parameters_dict["experiment_name"]  + "_scan_number_" + str(scan) + ".csv"
    file_path = os.path.join(data_folder, file_name)

    # Create a string storing relevant experiment data
    experiment_params = str(f"Date: {date_string},Experiment parameters\n  time zero: {time_zero}ps,time constant: {time_constant}s,Filter slope: {clfun.request_filter_slope(adapter)}dB/Oct,Input range: {clfun.request_range(adapter)}")

    # Write the parameters and data to a CSV file

    # Add the parameters as a comment line
    with open(file_path, "w") as file:
        file.write(f"# {experiment_params}\n")  

    # Append the rest of the data to the csv
    data_df.to_csv(file_path, index=False, mode="a", lineterminator="\n")

    # Save live graph aswell
    file_name = parameters_dict["experiment_name"] + "_scan_number_" + str(scan) + ".png"
    file_path = os.path.join(data_folder, file_name)
    fig.savefig(file_path, dpi=300)  # Save with high resolution

    # Append completed scan to global list
    Scans.append(Photodiode_data)

    return data_df



def close_devices(Troubleshooting=False):
    ########################### Close the device ###########################
    lib.BMC_StopPolling(serial_num, channel) # Does not return error codes
    
    result = lib.BMC_Close(serial_num)
    time.sleep(1)
    if result != 0:
        raise Exception(f"Error when closing devices\nfunction BMC_Close() failed: {clfun.get_error_description(result)}")
    elif Troubleshooting:
        print(f"BMC_Close passed without raising errors")
    
    print(f"Succesfully closed communications to Delay Stage")

    clfun.close_connection(adapter)
    print("Succesfully closed connection to lockin")

    return True
            
