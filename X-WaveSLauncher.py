import tkinter as tk
from tkinter import ttk
from tkinter import Toplevel
from tkinter import messagebox
import json
import core_logic
import threading
import sys
import queue
from functools import partial
from math import ceil
from tkinter import simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import os
import datetime
import webbrowser
import numpy as np

# Are you trying to troubleshoot with prints but they are redirected to the logs, maybe messagebox errors not verbose enough?
# Change the following bool to True
print_on_cmd = False

# TO DO list revised by Cris and Ankit: (Deadline: 1st of April)
# 
#   · Append gain at every step when autorangingat every step                  [ ]
#
#   · Lockin initialized to values writen on default_config.json               [ ]
#
#
# Less important TO DO list: No order in particular
#   · Define waiting time and number of pulses averaged and store in csv
#   · Implement loading different experiment presets, right now there only one, default, and the 
#     user overwrites it to save a preset.
#   · Move functions on GUI.py to their own library
#
#
# User Notes:
#   · Changing Windows font can hide some widgets! This GUI was designed for default windows screen parameters
#   · Careful using NI-Visa on the computer this software runs on, I had to delete it bc it was causing problems but 
#     it oculd've been because part of my installation was manually deleted... still
 


############################### Global variables ###############################
# This boolean flag prevents launching an experiment without
# waiting for the initialization to complete, using a flag 
# allows the user to configure the experiment while the 
# initialization is taking place
initialized = False
entries = {}
previous_scans = []
line_object = None
lines_list = []
prev_scan = 0
Scans = []
first_iteration = False
average_line_object = None
finishing_time_str = ''


# These variables are initialized as None so that we can check if they have 
# been intialized later on and perform some action (plt.close, join etc) that
# way we don't risk trying to close a non initialized variable 
adapter = None
fig = None
initialization_thread = None
experiment_thread = None

cmap = plt.get_cmap('inferno')

# Queue object to send data from experiment thread back 
experiment_data_queue = queue.Queue()    # Sends data from experiment thread to be graphed at GUI
abort_queue = queue.Queue()              # Sends abort signal from GUI to experiment thread to end func safely
error_queue = queue.Queue()              # Sends Exceptions caught in experiment and initialization threads 
                                   # to be displayed on GUI 



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
    Scans_ls = Completed_scans
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



def show_screen_from_menu(screen_name):
    """ Wrapper function to use `show_screen` inside OptionMenu """
    show_screen(screen_name, "Screen frame")  # Default to showing the main screen frame




def show_screen(screen_name, frame_type):
    # This function switches between frames, this could be a
    # switch between screens, specificaly to screen "screen_name" 
    # or between frames on a screen, to specify this we use the
    # variable "frame_type". These are really just keys on the 
    # following dict storing references to these frames
    #
    # The data structure for the Screens dict is as follows:
    #
    # Screens = {
    #     "Initialization screen": {
    #         "Screen frame": "Init_parent_frame",
    #         "Child frame": {}
    #         },
    # 
    #     "Experiment screen": {
    #         "Screen frame": "Exper_parent_frame", 
    #         "Child frame": "Exper_child_frame"
    #         }
    # }


    for _, frames in Screens.items():

        # Skip erasing child frames that dont exist
        if frames[frame_type] == None:
            continue

        # Whipe out the GUI by erasing all screen frames
        # which also erases all child frames
        frames[frame_type].grid_forget()

    # Show the selected frame
    Screens[screen_name][frame_type].grid(row=2, column=0, sticky="ew") # Row 2 because we always have the separator and menuvar on top



def close_window(window):
    window.destroy()



# Function to redirect stdout and stderr to a Queue
class OutputRedirector:
    def __init__(self, queue_obj):
        self.queue = queue_obj

    def write(self, message):
        if message.strip():  # Avoid empty lines
            self.queue.put(message)

    def flush(self):
        pass  # Required for compatibility


def capture_output(queue_obj, print_on_cmd):
    """
    Redirect both stdout and stderr to the provided Queue.
    """
    if not print_on_cmd:
        sys.stdout = OutputRedirector(queue_obj)
        sys.stderr = OutputRedirector(queue_obj)



def restore_output():
    """
    Restores the original stdout and stderr.
    """
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


def initialization_thread_logic():
    
    # Catch exceptions while initializing and display them
    # later to user to aid troubleshooting 
    try:
        core_logic.initialization(Troubleshooting=False)
        #core_logic.initialization_dummy(Troubleshooting=False)

    # Exceptions dont propagate upwards when using threads, we have to send it to main code through a Queue
    except Exception as e:
        error_queue.put(Exception(f"An error occured when initializing in function core_logic.initialization():\n{e}"))

    finally:
        restore_output()



def experiment_thread_logic(parameters_dict, experiment_data_queue, abort_queue, fig, num_scans, monitoring_window, error_measurement_type, autoranging_type):
    
    # Catch exceptions while initializing and display them
    # later to user to aid troubleshooting 
    try:
        for scan in range(0, num_scans):

            # Perform experiment and get data at the end
            abort_queue.put(False)  # before we start the experiment we reset the abort flag to false
            global Scans
            result = core_logic.perform_experiment(parameters_dict, 
                                                   experiment_data_queue, 
                                                   abort_queue, 
                                                   fig, 
                                                   scan, 
                                                   num_scans, 
                                                   error_measurement_type,
                                                   autoranging_type,
                                                   Scans) 

            # User has chosen to abort experiment and thus we receive an error code instead
            if isinstance(result, int):
                restore_output()
                close_window(monitoring_window)
                return None

            # The scan completed and we store it to compare against the new scan
            else:
                # We append the label for this experiment to the dataframe to 
                # use it as a label when graphing
                data_df = result
                data_dict = data_df.to_dict()
                data_dict["Scan number"] = scan          

                # Preserve data from previous scans to graph with 
                global previous_scans
                previous_scans.append(data_dict)

            #core_logic.perform_experiment_dummy(Troubleshooting=False)

    # Exceptions dont propagate upwards when using threads, we have to send it to main code through a Queue
    except Exception as e:
        error_queue.put(Exception(f"An error occured during the experiment:\n{e}"))
    
    finally:
        restore_output()
        


def initialize_button(default_values_delay_stage):

    # First validate that delay stage was configured to safe parameters
    Acceleration_mm_per_s2 = default_values_delay_stage["Acceleration_mm_per_s2"]
    MaxVelocity_mm_per_s = default_values_delay_stage["MaxVelocity_mm_per_s"]

    validation_rules_file_path = 'Utils/validation_rules.json'
    try:
        with open(validation_rules_file_path, "r") as json_file:
            validation_rules = json.load(json_file)
    except Exception as e:
        raise Exception(f"An error occured when opening {validation_rules_file_path}\n{e}")


    valid_parameter, _ = is_value_valid("Acceleration_mm_per_s2", Acceleration_mm_per_s2, validation_rules["Acceleration_mm_per_s2"])
    if not valid_parameter:
            return
    
    valid_parameter, _ = is_value_valid("MaxVelocity_mm_per_s", MaxVelocity_mm_per_s, validation_rules["MaxVelocity_mm_per_s"])
    if not valid_parameter:
            return

    # Create the waiting window
    waiting_window = Toplevel(main_window)
    waiting_window.title("Initializing Devices")
    waiting_window.geometry("450x300")
    #waiting_window.grab_set()  # Make it modal (blocks interaction with other windows)

    # Create a Listbox to display initialization messages
    listbox = tk.Listbox(waiting_window, selectmode=tk.SINGLE, height=15)
    scrollbar = tk.Scrollbar(waiting_window, orient=tk.VERTICAL)

    # Place Listbox and Scrollbar using grid()
    listbox.grid(row=0, column=0, sticky="ew")  # Expand in all directions
    scrollbar.grid(row=0, column=1, sticky="ns")  # Stretch only vertically

    # Configure the scrollbar
    listbox.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=listbox.yview)

    # Configure the parent (waiting_window) to allow expansion
    waiting_window.grid_rowconfigure(0, weight=1)  # Allow row 0 to expand
    waiting_window.grid_columnconfigure(0, weight=1)  # Allow column 0 to expand (Listbox)

    # Add a label to inform the user
    label = tk.Label(waiting_window, text="Please wait while the devices are initialized...")
    label.grid(row=1, column=0, padx=20, pady=20, sticky="n")

    # Queue for communication between threads
    output_queue = queue.Queue()

    # Redirect stdout and stderr to the queue
    capture_output(output_queue, print_on_cmd=False)

    # Get kinesis library path to delegate to the user appropiately tracking it's location uwu
    try:
        # Extract default configuration values for both devices from the configuration file
        default_config_file_path = 'Utils\default_config.json'
        with open(default_config_file_path, "r") as json_file:
            default_config = json.load(json_file)
            
    except Exception as e:
        raise Exception(f"An error occured when opening {default_config_file_path}\n{e}")
    
    # Run initialization on a different thread
    initialization_thread = threading.Thread(target=initialization_thread_logic)
    initialization_thread.start()

    # Function to check for updates from the queue
    def check_for_updates():
        while not output_queue.empty():
            new_message = output_queue.get()
            listbox.insert(tk.END, new_message)
            listbox.see(tk.END)  # Auto-scroll to the bottom

        if initialization_thread.is_alive():
            waiting_window.after(100, check_for_updates)

        else:
            initialization_thread.join()
            label.config(text="Initialization Complete")

            global initialized
            initialized = True

            # Add button to close window
            # IDK why this button does not show in the GUI but since it does the same as manually closing the window
            # I'll ignore it for now (probably forever if you are reading this)
            button = tk.Button(waiting_window, text="Ok", command=partial(close_window, waiting_window))
            button.grid(row=1, column=1, padx=20, pady=20, sticky="s")

    # Start checking for updates
    #check_for_updates(output_queue, listbox, initialization_thread, waiting_window, label)
    check_for_updates()



# OVERSIGHT: If the rules dict doesn't have a "type" key 
# before the rest of keys it is possible that the parameter is not parsed
# before attempting to check other rules and the function will fail
# when trying illegal operation like substraction on strings!!!
def is_value_valid(parameter_name, parameter_value, parameter_rules):
    '''
    This function takes a value that's previously been fetched from 
    the user and checks whether the value adheres to certain rules 
    located on a "rules" dict, it returns a True if the value checks 
    all rules or a False whenever oneor more rules are not checked. Additionaly
    it returns the value correctly casted to it's specified type
    '''

    # If there are no rules for this particular value 
    # we break away from this function early
    if not parameter_rules:
        return True, parameter_value
    
    # If there rules for it we iterate through the dict of rules
    for rule_type, rule_value in parameter_rules.items():

        # Some rules check whether the type of data input is correct
        # They also do the parsing for the following rule checks
        if rule_type == "type":

            # If the value is expected to be a string but its not
            # we return a false and inform the user
            if rule_value == "str":
                try: 
                    isinstance(parameter_value, str)

                # If isinstance fails it means there is not a string
                except ValueError:
                    return False, None

            # In this case we must first attempt to cast to string since
            # all values retreived from screen are retreived as strings
            if rule_value == "float":    
                
                try:
                    parameter_value = float(parameter_value)

                except ValueError:
                    messagebox.showinfo("Error", f"Parameter {parameter_name} is not a valid floating point number, please use .  as decimal separator")
                    return False, None

        # Other rules specify a range of values

        # This is kind of hacky but some parameters_values are specified in relative time and others in absolute time
        # (see help file for an explanation on asolute and relative time) To solve this we gotta substract time_zero to compare
        # absolute parameter values against relative limit delays. 
        time_zero =  float(entries["time_zero"].get())
        if rule_type == "max_abs" and parameter_value > rule_value - time_zero:
            
            messagebox.showinfo("Error", f"Parameter {parameter_name} is above maximum limit: {rule_value - time_zero}\n")
            return False, None
        
        if rule_type == "min_abs" and parameter_value < rule_value - time_zero:
            messagebox.showinfo("Error", f"Parameter {parameter_name} is below minimum limit: {rule_value - time_zero}")
            return False, None
        
        if rule_type == "max_rel" and parameter_value > rule_value:
            
            messagebox.showinfo("Error", f"Parameter {parameter_name} is above maximum limit: {rule_value}")
            return False, None
        
        if rule_type == "min_rel" and parameter_value < rule_value:
            messagebox.showinfo("Error", f"Parameter {parameter_name} is below minimum limit: {rule_value}")
            return False, None
    

    # After all rules are check we can return a boolean flag indicating
    # a valid value and the correctly parsed value
    return True, parameter_value



def get_parse_validate_screen_params(entries_widgets):
    '''
    This function gets user values from entries on the screen into a new 
    temporary dict with the same structure as the one holding the 
    default values. It parses them properly and it checks whether the values
    are valid, if they are it will save them on a json, if not it will inform
    the user of the error. 
    '''

    # We construct a dict holding the values input by the user
    # Note: The get method returns all values as strings so we'll 
    # have to parse them later
    screen_values = {}
    for parameter_name, _ in entries_widgets.items():

        # Each entry is read with get from the widgets stored in 
        # the entries dict, this dict was constructed wth the same
        # keys as leg_parameters
        screen_values[parameter_name] = entries_widgets[parameter_name].get()

    # Construct dict holding validation rules for each value
    validation_rules_file_path = 'Utils/validation_rules.json'
    try:
        with open(validation_rules_file_path, "r") as json_file:
            validation_rules = json.load(json_file)
    
    except Exception as e:
        raise Exception(f"An error occured when opening {validation_rules_file_path}\n{e}")


    # Check that each parameter verifies all validation rules
    for parameter_name, value in screen_values.items():
        
        # The funciton returns a boolean flag indicating whether the parameter
        # input by the user is valid or not, if it's valid it also returns the
        # parameter properly parsed to it's type
        valid_parameter, parsed_value = is_value_valid(parameter_name, value, validation_rules[parameter_name])

        # If the parameter is not valid we break early and indicate there was a problem
        if not valid_parameter:
            return False, {}
        
        # If the parameter is valid and we are able to parse it we store it on the dict containing
        # the parsed values
        else:
            screen_values[parameter_name] = parsed_value
    
    # If all parameters check we return a true and the parameters properly parsed
    return True, screen_values



def save_parameters(experiment_preset):
    
    global entries
    
    try:
        trip_legs = experiment_preset["trip_legs"]


        ### We first validate that the time zero parameter is safe (all absolute parameters reference time zero)
        validation_rules_file_path = 'Utils/validation_rules.json'
        try:
            with open(validation_rules_file_path, "r") as json_file:
                validation_rules = json.load(json_file)
        except Exception as e:
            raise Exception(f"An error occured when opening {validation_rules_file_path}\n{e}")


        valid_parameter, _ = is_value_valid("time_zero", 
                                                       entries["time_zero"].get(), 
                                                       validation_rules["time_zero"])
        if not valid_parameter:
                return

        ### We then proceed to validate all other risky parameters

        # We create empty presets to store parameters after validation
        trip_legs_entries = entries["trip_legs"]
        experiment_preset_save = {}
        trip_legs_save = {}
        #for leg_number, leg_parameters in trip_legs.items():
        for leg_number, leg_parameters in trip_legs_entries.items():
            valid_parameters, screen_parameters = get_parse_validate_screen_params(leg_parameters)
        
            # If any of the parameters is not valid we return
            if not valid_parameters:
                return
            
            # If the parameters for this particular leg were correct we keep them on a dict
            trip_legs_save[leg_number] = screen_parameters


        # Finally we construct a dict to save it by getting the parameters from screen that don't need to save the validated
        experiment_preset_save["experiment_name"] = entries["experiment_name"].get()
        experiment_preset_save["time_constant"] = float(entries["time_constant"].get())
        experiment_preset_save["roll_off"] = int(entries["roll_off"].get())
        experiment_preset_save["error_measurement_type"] = str(entries["error_measurement_type"].get())
        experiment_preset_save["autoranging_type"] = str(entries["autoranging_type"].get())
        experiment_preset_save["time_zero"] = float(entries["time_zero"].get())
        experiment_preset_save["num_scans"] = int(entries["num_scans"].get())
        experiment_preset_save["trip_legs"] = trip_legs_save
        
        # After all tests have passed we save them into a json
        with open('Utils\experiment_preset.json', "w") as json_file:
        
            json.dump(experiment_preset_save, json_file)
        
            messagebox.showinfo("Parameters saved", f"Parameters were succesfully saved")
        
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")



def launch_experiment(experiment_data_queue):

    try:
        global entries

        if not initialized:
            messagebox.showinfo("Error launching experiment", "Please start/wait for device initialization to complete before launching experiment")
            return

        ### First we'll verify parameters are safe before launching the experiment
        
        # Extract references to data we wanna validate
        Legs_entries = entries["trip_legs"]

        # Construct a dict that will store the parsed verified data to later feed to the delay stage
        experiment_parameters = {
            "experiment_name": entries["experiment_name"].get(), 
            "time_constant": float(entries["time_constant"].get()),
            "roll_off": int(entries["roll_off"].get()),
            "time_zero":float(entries["time_zero"].get()),
            "num_scans":int(entries["num_scans"].get()) 
            }
        
        trip_legs_parsed = {}


        ### We first validate that the time zero parameter is safe (all absolute parameters reference time zero)
        validation_rules_file_path = 'Utils/validation_rules.json'
        try:
            with open(validation_rules_file_path, "r") as json_file:
                validation_rules = json.load(json_file)
        except Exception as e:
            raise Exception(f"An error occured when opening {validation_rules_file_path}\n{e}")


        valid_parameter, _ = is_value_valid("time_zero", 
                                                       entries["time_zero"].get(), 
                                                       validation_rules["time_zero"])
        if not valid_parameter:
                return

        ### We then proceed to validate all other risky parameters

        # Validate and parse iteratively
        for leg_number, leg_entries in Legs_entries.items():

            # For each leg parameters we estimate and accumulate it's duration
            # First get parameters from screen and verify they are valid
            valid_parameters, parsed_values = get_parse_validate_screen_params(leg_entries)

            if valid_parameters:
                trip_legs_parsed[leg_number] = parsed_values
            
            else:
                return
        
        experiment_parameters["trip_legs"] = trip_legs_parsed

        # Then we check whether an output folder of the same name is in danger of being overwritten
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_folder = os.path.join(current_dir, "Output")
        data_folder = os.path.join(output_folder, entries["experiment_name"].get())

        if os.path.exists(data_folder):

            messagebox.showerror("Error", "Choosing the same experiment file name will overwrite the data for the previous experiment with the same name\nPlease change experiment file name")
            return 
                

        ### Once parameters are verified and parsed we proceed with the experiment launch

        ### Create a window to monitor experiment
        monitoring_window = Toplevel(main_window)
        monitoring_window.title("Experiment in progress")
        monitoring_window.geometry('1920x1080')
        monitoring_window.resizable(True, True)
        monitoring_window.grab_set()  # Make it modal (blocks interaction with other windows)

        # Configure grid weights for entire
        monitoring_window.grid_rowconfigure(0, weight=1)  # Allow vertical expansion
        monitoring_window.grid_columnconfigure(0, weight=1)  # Logging column
        monitoring_window.grid_columnconfigure(2, weight=4)  # Graph gets 4x more space than log

        ### Create scrollable log

        # Create a Listbox to display initialization messages
        listbox = tk.Listbox(monitoring_window, selectmode=tk.SINGLE, height=15)
        scrollbar = tk.Scrollbar(monitoring_window, orient=tk.VERTICAL)

        # Place widgets using grid
        listbox.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(padx=20, pady=20, row=0, column=1, sticky="ns")

        # Configure scrollbar
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        # Add a label to inform the user
        label = tk.Label(monitoring_window, text="Please wait while the experiment takes place...")
        label.grid(padx=20, pady=20)



        ### Create live graph

        # Create figure and axes
        fig, axes = plt.subplots(figsize=(10, 5), dpi=100)
        axes.set_xlabel('t [ps]')
        axes.set_ylabel('PD [Vrms]')

        # Create an empty graph to grab a reference for the line object, this is the curve on the graph
        # and we'll update it for every new data point, we do this because updating preserves user 
        # zoom and pan on the graph. Simply redrawing the whole graph would reset them
        global line_object, lines_list, cmap
        line_object, = axes.plot([], [], linestyle='-', color=cmap(0), label="scan 0")
        lines_list.append(line_object)
        axes.set_xlabel('t [ps]')
        axes.set_ylabel('PD [Vrms]')

        # Frame for Graph
        graph_frame = tk.Frame(monitoring_window)
        graph_frame.grid(padx=20, pady=20, row=0, column=2, sticky="ew")

        # Canvas for Matplotlib
        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Add Navigation Toolbar for Zoom and Scroll on it's own 
        # toolbar because NavigationToolbar2Tk() internally uses pack() which conflicts
        # with the rest of my code which uses grid()
        toolbar_frame = tk.Frame(graph_frame)
        toolbar_frame.grid(row=1, column=0, sticky="ew")

        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Inform user of finishing time
        estimate_experiment_timespan(GUIless=True)
        global finishing_time_str
        label = tk.Label(graph_frame, text=f"Experiment will finish at around {finishing_time_str}")
        label.grid(padx=20, pady=20, row=2, column=0, sticky="ew")



        ### Create a button to abort experiment by changing the following flag
        # Launch experiment will check this global flag at each loop
        def abort_experiment():
            messagebox.showinfo("Wait", f"Stopping experiment\nThis may take a couple steps\nPlease wait while experiment closes window safely before launching a new experiment.")
            abort_queue.put(True)

            # Close figure
            plt.close(fig)

            # Clear previous data
            '''global previous_scans, Scans'''
            global previous_scans, Scans, finishing_time_str
            previous_scans = []
            Scans = []
            finishing_time_str = ''


        Stop_early_button = tk.Button(monitoring_window, text="Stop experiment early", command=abort_experiment)
        Stop_early_button.grid(row=1, column=1, padx=10, pady=5, sticky="w")



        # Queue for reading prints from core_logic functions and displaying them on listbox
        output_queue = queue.Queue()

        # Redirect stdout and stderr to the queue. We capture prints that would go into the command line
        # and redirect them to the experiment log
        capture_output(output_queue, print_on_cmd=False)

        # Run experiment on a different thread
        num_scans = int(entries["num_scans"].get())
        error_measurement_type = str(entries["error_measurement_type"].get())
        autoranging_type = str(entries["autoranging_type"].get())
        experiment_thread = threading.Thread(target=experiment_thread_logic, 
                                                args=(experiment_parameters, 
                                                      experiment_data_queue, 
                                                      abort_queue, 
                                                      fig, 
                                                      num_scans, 
                                                      monitoring_window, 
                                                      error_measurement_type,
                                                      autoranging_type))
        experiment_thread.start()

        global prev_scan
        prev_scan = 0

        # Function to check for updates from the queue.
        # Proceed with caution, this is one of the hackiest most convoluted functions in this project...
        # If you have to troubleshoot this... well Im sorry for you.
        def monitor_experiment():

            global line_object, lines_list, prev_scan, cmap, first_iteration, average_line_object

            # First we wait for a command print from perform_experiment()
            # once we receive it we print it in the log and continue with graphing
            while not output_queue.empty():
                new_message = output_queue.get()
                listbox.insert(tk.END, new_message)
                listbox.see(tk.END)  # Auto-scroll to the bottom
            
            # Update GUI as long as the experiment is taking place
            if experiment_thread.is_alive():

                # Only update graph whenever new data is acquired
                if not experiment_data_queue.empty():

                    # Get data from experiment thread
                    data_packet = experiment_data_queue.get()
                    positions = data_packet["Positions"]
                    photodiode_data = data_packet["Photodiode data"]
                    photodiode_data_errors = data_packet["Photodiode data errors"]
                    scan_number = int(data_packet["Scan number"])
                    live_average = data_packet["Live average"]


                    # If we detect that arriving data corresponds to a new scan we
                    # create a new line object to draw on a different curve
                    if scan_number > prev_scan:

                        # We first compute the color for the line 
                        max_scans = experiment_parameters["num_scans"]
                        color_fraction = scan_number / max_scans
                        new_color = cmap(color_fraction)

                        # We then generate a new line object and append it to the list
                        new_line_object, = axes.plot([], [], linestyle='-', color=new_color, label=f"scan {scan_number}")
                        lines_list.append(new_line_object)
                        line_object = new_line_object
                        prev_scan = scan_number

                        # And generate a new line object for the average, but we only need to draw one
                        # average so
                        
                        if first_iteration:
                            average_line_object, = axes.plot([], [], linestyle='--', linewidth=3, color="deepskyblue", label=f"Average")

                            # Make sure we don't create any new average line objects on the following scans
                            first_iteration = False

                    
                    # We update only the last line, corresponding to current scan data
                    # that way we keep the curves for the previous scans untouched
                    line_to_update = lines_list[-1]

                    # Update graph with new data
                    line_to_update.set_xdata(positions[:len(photodiode_data)])
                    line_to_update.set_ydata(photodiode_data)

                    # We then update the average if there is one to average
                    if average_line_object is not None and live_average is not None:
                        average_line_object.set_xdata(positions)
                        average_line_object.set_ydata(live_average)

                    axes.relim()           # Recompute the data limits based on current data
                    axes.autoscale_view()  # Auto-adjust the view to the new limits
                    axes.legend()

                    # Update Canvas
                    canvas.draw()


                # Update the monitoring window at 10ms intervals
                monitoring_window.after(10, monitor_experiment)



            # Close experiment thread after it's done
            else:
                experiment_thread.join()
                label.config(text="Experiment completed")

                # Clear previous data
                global previous_scans, Scans, finishing_time_str
                previous_scans = []
                Scans = []
                finishing_time_str = ''

                # Remove stop early button from screen
                Stop_early_button.destroy()

                # Close figure
                plt.close(fig)


        # Start monitoring the experiment
        global first_iteration
        first_iteration = True
        monitor_experiment()
        

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")
        plt.close(fig)
        




def estimate_experiment_timespan(GUIless=False):

    try:        
        global entries, adapter

        # Grab parameters defining experiment length
        Legs_entries = entries["trip_legs"]
        time_constant = float(entries["time_constant"].get())
        roll_off = int(entries["roll_off"].get())
        num_scans = int(entries["num_scans"].get())
        settling_time = core_logic.request_settling_time(time_constant, filter_slope=roll_off, verbose=False)
        estimated_duration = 0


        ### We first validate that the time zero parameter is safe (all absolute parameters reference time zero)
        validation_rules_file_path = 'Utils/validation_rules.json'
        try:
            with open(validation_rules_file_path, "r") as json_file:
                validation_rules = json.load(json_file)
        except Exception as e:
            raise Exception(f"An error occured when opening {validation_rules_file_path}\n{e}")


        valid_parameter, _ = is_value_valid("time_zero", 
                                                       entries["time_zero"].get(), 
                                                       validation_rules["time_zero"])
        if not valid_parameter:
                return

        ### We then proceed to validate all other risky parameters

        # Iterate through dict containing all trip legs
        for leg_entries in Legs_entries.values():

            # For each leg parameters we estimate and accumulate it's duration
            # First get parameters from screen and verify they are valid
            valid_parameters, screen_values = get_parse_validate_screen_params(leg_entries)

            if valid_parameters:
                
                ### Calculate time speint on each step 

                # Get the relevant parameters
                start_position = screen_values["abs time start [ps]"]
                end_position = screen_values["abs time end [ps]"]
                step_size = screen_values["step [ps]"]

                average_step_duration_sec = 2.2 + settling_time # Moving + settling time
                average_step_duration_sec += 1.1 # Capturing data
                
                # Add up time to every step depending on step configuration
                error_measurement_type = entries["error_measurement_type"].get()
                if error_measurement_type == "At every point":
                    average_step_duration_sec += 2.2

                autoranging_type = entries["autoranging_type"].get()
                if autoranging_type == "At every point":
                    # Autoscale
                    average_step_duration_sec += 1.2

                    # Autorange
                    average_step_duration_sec += 0.1

                ### Accumulate for all steps on each leg                
                num_steps = ceil( (end_position - start_position) / step_size )
                estimated_duration += int(average_step_duration_sec * num_steps )

            if not valid_parameters:
                return None

        # Finally multiply times the amount of scans selected
        estimated_duration = estimated_duration * num_scans

        # Add up one final time at the end when the user asks to only measure errors once
        error_measurement_type = entries["error_measurement_type"].get()
        if error_measurement_type == "Once at the start":
            estimated_duration += 2.2

        autoranging_type = entries["autoranging_type"].get()
        if autoranging_type == "Once at time zero":
 
            # Autoscale
            estimated_duration += 1.2

            # Autorange
            estimated_duration += 0.1

        # At the end of the estimation we create a message for the user
        estimation_message = ""

        # It would also be useful for the user to know when the experiment will end so that they can 
        # set a timer and leave the lab. For this we estimate the datetime at the end of estimated_duration
        time_now = datetime.datetime.now()
        finishing_time = time_now + datetime.timedelta(0, estimated_duration)

        # When estimated duration is below 1 min we give an estimation in seconds
        # to make it more readable
        global finishing_time_str
        if estimated_duration < 60:
            finishing_time_str = str(finishing_time.strftime("%H:%M:%S"))
            estimation_message = str(estimated_duration) + " seconds\nFinishing at around " + finishing_time_str

        # Readability for experiments below an hour
        elif estimated_duration < 60*60:
            estimated_duration_mins = int(estimated_duration / 60)
            estimated_duration_secs = int(estimated_duration % 60)

            finishing_time_str = str(finishing_time.strftime("%H:%M:%S"))
            estimation_message = f"{estimated_duration_mins} minutes and {estimated_duration_secs} seconds\nFinishing at around " + finishing_time_str

        # Experiments below a day
        elif estimated_duration < 60*60*24:
            estimated_duration_hours = int(estimated_duration / (60*60))
            estimated_duration_mins = int((estimated_duration % (60*60))/60)

            finishing_time_str = str(finishing_time.strftime("%H:%M"))
            estimation_message = f"{estimated_duration_hours} hours and {estimated_duration_mins} minutes\nFinishing at around " + finishing_time_str
        
        # Experiments above
        elif estimated_duration >= 60*60*24:
            estimated_duration_days = int(estimated_duration / (60*60*24))

            finishing_time_str = str(finishing_time.strftime("%d/%m/%Y, %H"))
            estimation_message = f"above {estimated_duration_days} days\nFinishing the " + finishing_time_str + "h\nDon't you think you are pushing it just a little?..."
        
        if not GUIless:
            messagebox.showinfo("Estimation", f"Experiment is estimated to take {estimation_message}")

    except ZeroDivisionError:
        messagebox.showerror("Error", f"An error occurred:\nZero length step size caused division by zero. Please enter a valid length")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")



def create_experiment_gui_from_dict(parameters_dict):

    experiment_name = parameters_dict["experiment_name"]
    time_constant = parameters_dict["time_constant"]
    roll_off = parameters_dict["roll_off"]
    error_measurement_type = parameters_dict["error_measurement_type"]
    autoranging_type = parameters_dict["autoranging_type"]
    time_zero = parameters_dict["time_zero"]
    trip_legs = parameters_dict["trip_legs"]
    num_scans = parameters_dict["num_scans"]
     

    experiment_parameters_frame = Screens["Experiment screen"]["Child frame"]

    # Erase previous screen by destroying all of it's children
    for widget in experiment_parameters_frame.winfo_children():
        widget.destroy()

    row_num = 1
    label = tk.Label(experiment_parameters_frame, text="Please input experiment parameters", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    row_num += 1

    # We will create a dict with an equal structure to our json, under the same keys we'll store 
    # the widgets for the entries, that is a way to get values from the screen
    global entries
    entries = {}

    # First we start with the entries that are not iterable (this snippet is not
    # very readable, please refer to the for loop below for comments)
    label = tk.Label(experiment_parameters_frame, text="experiment file name (avoid special characters)", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(experiment_parameters_frame)
    entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entry.insert(0, experiment_name)
    entries["experiment_name"] = entry
    row_num += 1

    # filter roll off can only be selected from a series of values
    filter_roll_off_table = [6, 12, 18, 24] # In dB/Oct

    # Create Combobox to select filter roll off from
    label = tk.Label(experiment_parameters_frame, text="filter roll-off [dB/oct]", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    combo = ttk.Combobox(experiment_parameters_frame, values=filter_roll_off_table, state="readonly")
    combo.set(roll_off)  # Default value
    combo.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entries["roll_off"] = combo
    row_num += 1

    # time constant can only be selected from a series of values
    time_constant_table = [1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3, 3e3, 10e3, 30e3]

    # Create Combobox to select time constant from
    label = tk.Label(experiment_parameters_frame, text="time constant [s]", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    combo = ttk.Combobox(experiment_parameters_frame, values=time_constant_table, state="readonly")
    combo.set(time_constant)  # Default value
    combo.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entries["time_constant"] = combo
    row_num += 1

    # Create Combobox to select how to measure errors
    error_measurement_table = ["Never", "Once at the start", "At every point"]
    label = tk.Label(experiment_parameters_frame, text="Error measurement type", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    combo = ttk.Combobox(experiment_parameters_frame, values=error_measurement_table, state="readonly")
    combo.set(error_measurement_type)  # Default value
    combo.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entries["error_measurement_type"] = combo
    row_num += 1

    # Create Combobox to select how to autorange
    autoranging_table = ["Never", "Once at time zero", "At every point"]
    label = tk.Label(experiment_parameters_frame, text="Autoranging type", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    combo = ttk.Combobox(experiment_parameters_frame, values=autoranging_table, state="readonly")
    combo.set(autoranging_type)  # Default value
    combo.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entries["autoranging_type"] = combo
    row_num += 1

    # Time zero input
    label = tk.Label(experiment_parameters_frame, text="rel time zero [ps]", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(experiment_parameters_frame)
    entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entry.insert(0, time_zero)
    entries["time_zero"] = entry
    row_num += 1

    # Number of scans input
    label = tk.Label(experiment_parameters_frame, text="Number of scans", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(experiment_parameters_frame)
    entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entry.insert(0, num_scans)
    entries["num_scans"] = entry
    row_num += 1

    # We now create the scrollable area holding the leg parameters

    # Create a Canvas widget inside out parameters frame
    canvas_legs = tk.Canvas(experiment_parameters_frame)
    canvas_legs.grid(row=row_num, column=0, sticky="nsew")  # Fill entire grid cell

    # Add a Scrollbar and link it to the Canvas
    scrollbar = tk.Scrollbar(experiment_parameters_frame, orient=tk.VERTICAL, command=canvas_legs.yview)
    scrollbar.grid(row=row_num, column=1, padx=10, pady=10, sticky="ns")  # Attach scrollbar to the right

    # Configure Canvas to use scrollbar
    canvas_legs.configure(yscrollcommand=scrollbar.set)

    # Create a Frame inside the Canvas (this will be the scrollable area)
    scrollable_frame = tk.Frame(canvas_legs)
    scrollable_frame.grid(row=row_num, column=0, padx=10, pady=10, sticky="nsew")

    canvas_legs.create_window((0, 0), window=scrollable_frame, anchor="nw")

    # Function to update scroll region
    def update_scroll_region(event=None):
        canvas_legs.configure(scrollregion=canvas_legs.bbox("all"))

    # Bind resizing event
    scrollable_frame.bind("<Configure>", update_scroll_region)

    
    # Now that the frame is scrollable we fill it with leg parameters

    trip_legs_entries = {}
    # trip_legs is a dict storing each leg with it's corresponding parameters
    for leg_number, leg_parameters in trip_legs.items():

        # For starters we keep the parameters for each leg into their own buffer dict
        trip_leg_entry = {}

        # Label at the start the number for the leg
        label = tk.Label(scrollable_frame, text=f"leg number {leg_number}", anchor="w")
        label.grid(row=row_num, column=0, padx=10, pady=15, sticky="w")
        row_num += 1

        # For each leg parameters we iteratively write them on screen
        for parameter, default_value in leg_parameters.items():

            # For every parameter the user will input add a short description with a label 
            label = tk.Label(scrollable_frame, text=parameter, anchor="w")
            label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

            # Add an entry box for the user to write a parameter on the cell and place it to the right
            entry = tk.Entry(scrollable_frame)
            entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")

            # Fill entry box with the default value
            entry.insert(0, str(default_value))
            
            # Store entries on a different dict to read their screen values later
            trip_leg_entry[parameter] = entry

            # Following labels and entry boxes will be written a row below
            row_num += 1
        
        # At the end of drawing and with all of the widgets for a certain leg retrieved 
        # we store the buffer dict into the dict holding all of the trips with it's appopiate key
        trip_legs_entries[leg_number] = trip_leg_entry
    
    # And at the end of the loop we append all of the trips to the main entries dict
    entries["trip_legs"] = trip_legs_entries
    

    # Show frames at the end
    experiment_parameters_frame.grid(row=2, column=0, sticky="ew")

    


def edit_trip_legs():

    try:
        global entries

        # We first ask the user to input number of legs in the trip
        num_legs = simpledialog.askstring("Input", "Please enter number of legs in the trip:")

        # If the user closes the simpledialog window without inputing a value simpledialog.asktring()
        # will return a None and we return early
        if num_legs is None:
            return None

        # If the user has input a value for the amount of legs we cast the it from str to int and proceed
        else:
            num_legs = int(num_legs)


        # We then construct a dict from which to construct the GUI later holding placeholder values
        # but we should still preserve parameters that the user might care for
        experiment_name = str(entries["experiment_name"].get())
        time_constant = float(entries["time_constant"].get())
        roll_off = int(entries["roll_off"].get())
        error_measurement_type = str(entries["error_measurement_type"].get())
        autoranging_type = str(entries["autoranging_type"].get())
        time_zero = float(entries["time_zero"].get())
        num_scans = int(entries["num_scans"].get())

        new_experiment_dict = {"experiment_name": str(experiment_name), 
                               "time_constant": str(time_constant), 
                               "roll_off": str(roll_off), 
                               "error_measurement_type": str(error_measurement_type), 
                               "autoranging_type": str(autoranging_type), 
                               "time_zero": str(time_zero), 
                               "num_scans": str(num_scans)}
        
        # We now append as many trip legs as requested
        new_legs = {}
        for leg_number in range(0, num_legs):
            new_legs[str(leg_number)] = {"abs time start [ps]": 0.0, "abs time end [ps]": 0.0, "step [ps]": 0.0}

        new_experiment_dict["trip_legs"] = new_legs

        # And proceed to construct a new frame with the placeholder data, passing these arguments deletes
        # the previously drawn frame Entries_Frame, experiment_preset
        create_experiment_gui_from_dict(new_experiment_dict)

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")


def open_help_file():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    help_file_path = os.path.join(current_dir, "Utils\X_WaveS_Automatic_Pump_Probe_Manual.pdf")

    try:
        could_open_file = webbrowser.open(r'file://' + help_file_path)

        if not could_open_file:
            print("Could not open help file")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")



def open_repository():
    try:
        could_open_file = webbrowser.open(r'https://github.com/Guilldeas/Pump_Probe_Measurement_Automatization')

        if not could_open_file:
            print("Could not open repository")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")



############################### MAIN CODE STARTS HERE ###########################
def main():

    ############################### Start drawing GUI ###############################
    # Create the main window
    global main_window
    main_window = tk.Tk()
    main_window.title("X-WaveSLauncher")
    
    # Get screen size
    #main_window.attributes('-fullscreen', True)
    main_window.geometry('1920x1080')


    # The whole code is inside a try loop, exceptions are allowed to propagate upwards and are caught at the end showing an error messagebox
    try:

        # Mysterious snippet
        day_of_the_week = datetime.datetime.today().weekday()
        if day_of_the_week == 5 or day_of_the_week == 6:
            response = messagebox.askokcancel("What a dedicated employee", "I get you, science is cool, but you are at the lab on a weekend.\nPerhaps you should close up for today and get some rest.\nWhat do you think?")
            
            if response:
                close_window(main_window)

        # Grab default configuration dict from default file
        try:
            # Extract default configuration values for both devices from the configuration file
            default_config_file_path = 'Utils\default_config.json'
            with open(default_config_file_path, "r") as json_file:
                default_config = json.load(json_file)
                
        except Exception as e:
            raise Exception(f"An error occured when opening {default_config_file_path}\n{e}")

        default_values_delay_stage = default_config["Delay Stage Default Config Params"]
        default_values_lockin = default_config["Lockin Default Config Params"]

        # There are different screens (frames) in this GUI, each serves a different function 
        # and must display different frames to change between them we must store them into a
        # dict after building them
        global Screens 
        Screens = {}
        # The data structure for the Screens dict is as follows:
        #
        # Screens = {
        #     "Initialization screen": {
        #         "Screen Frame": "Init_parent_frame",
        #         "Child frames": {}
        #         },
        # 
        #     "Experiment screen": {
        #         "Screen Frame": "Exper_parent_frame", 
        #         "Child frame": "Exper_child_frame_1"
        #         }
        # }
        #
        # Screens on the GUI are drawn with frames and stored as parent frames, these 
        # need to be erased and drawn whenever the user changes screens so we need to 
        # keep track of them in this dict, however sometimes the user will edit the 
        # number of entries on the screen and we'll need to erase and redraw only certain 
        # parts of the screen so we'll also keep these child frames on a child dict


        ################################### Initialization Screen #########################
        # We create a frame that will contain everything under this screen, this frame will
        # be shown or hidden depending on what screen we want to display
        Initialization_screen = tk.Frame(main_window)

        Initialization_screen.grid(row=2, column=0, padx=10, pady=10)
        #third_label = tk.Label(Initialization_screen, text="Third row label Child", anchor="w")
        #third_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
            

        Screens["Initialization screen"] = {}
        Screens["Initialization screen"]["Screen frame"] = Initialization_screen
        Screens["Initialization screen"]["Child frame"] = None


        # Add text (label) prompting user to introduce configuration parameters
        label = tk.Label(Initialization_screen, text="Device initialization parameters (Read only, edit from Utils/default_config.json)", anchor="w")
        label.grid(row=0, column=0, padx=10, pady=5)

        # The widgets will be placed in a grid with respect to each other,
        # to define their separation we define a "no place" x and y pad radius measured 10px around them
        # finally we specify "w" to format them to the left or west of their "cell"
        label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        # Place an empty label at the end to add some space
        spacer = tk.Label(Initialization_screen, text="")  # An empty label
        spacer.grid(row=2, column=0, pady=10)  # Adds vertical space



        ############################### Frame for delay stage ###############################
        # To create a section we use a frame which we will treat code wise as a window in which 
        # to place our widgets, this has the added benefit of referencing these widgets on a new subgrid, 
        # it's more modular too since we can rearrange the whole frame without loosing the reference
        # between widgets  

        # We place the frame indexing it to the initialization screen frame
        delay_parameters_frame = tk.Frame(Initialization_screen)
        delay_parameters_frame.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        row_num = 0
        label = tk.Label(delay_parameters_frame,  # Instead of placing the widget in the main window we now place it on the frame
                            text="Delay stage parameters",
                            anchor="w")
        label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
        row_num += 1


        for parameter, default_value in default_values_delay_stage.items():

            # For every parameter add a short description with a label 
            label = tk.Label(delay_parameters_frame, text=parameter, anchor="w")
            label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

            # Add an entry box for the user to write a parameter on the cell and place it to the right
            entry = tk.Entry(delay_parameters_frame)
            entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")

            # Fill entry box with the default value
            entry.insert(0, str(default_value))

            # Following labels and entry boxes will be written a row below
            row_num += 1

        # Spacing at the end of the section with empty labels
        spacer = tk.Label(delay_parameters_frame, text="")  # An empty label
        spacer.grid(row=row_num, column=0, pady=10)  # Adds vertical space



        ############################### Frame for lockin ###############################
        # Repeat for lockin parameters
        lockin_parameters_frame = tk.Frame(Initialization_screen)
        lockin_parameters_frame.grid(row=4, column=0, padx=10, pady=10, sticky="w")

        row_num = 0
        label = tk.Label(lockin_parameters_frame, text="Lock-in parameters", anchor="w")
        label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
        row_num += 1

        # Add labels in succession
        for parameter, default_value in default_values_lockin.items():

            # For every parameter the user will input add a short description with a label 
            label = tk.Label(lockin_parameters_frame, text=parameter, anchor="w")
            label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

            # Add an entry box for the user to write a parameter on the cell and place it to the right
            entry = tk.Entry(lockin_parameters_frame)
            entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")

            # Fill entry box with the default value
            entry.insert(0, str(default_value))

            # Following labels and entry boxes will be written a row below
            row_num += 1

        # This button initializes the devices prior to running the experiment
        button = tk.Button(Initialization_screen, text="Initialize devices", command=partial(initialize_button, default_values_delay_stage))
        button.grid(row=5, column=0, padx=10, pady=5, sticky="w")




        ################################### Experiment Configuration Screen #########################
        # This screen holds the parameters to configure the experiment and visualize it
        Experiment_screen = tk.Frame(main_window)
        Screens["Experiment screen"] = {}
        Screens["Experiment screen"]["Screen frame"] = Experiment_screen

        # Load experiment configuration parameters
        experiment_preset_file_path = 'Utils\experiment_preset.json'
        try:
            with open(experiment_preset_file_path, "r") as json_file:
                experiment_preset = json.load(json_file)
        
        except Exception as e:
            raise Exception(f"An error occured when opening {experiment_preset_file_path}\n{e}")

        # Create a frame for the entries alone so we can overwrite them when the user decides to add legs to the trip
        Entries_frame = tk.Frame(Experiment_screen)

        # We store this frame as a child frame of the Experiment screen frame
        Screens["Experiment screen"]["Child frame"] = Entries_frame

        # Initially we draw the GUI for the input loaded from the experiment preset into a dict
        create_experiment_gui_from_dict(experiment_preset)

        # We now ask the user if they want to edit the number of legs on the trip
        button = tk.Button(Experiment_screen, text="Edit number of trip legs", command=edit_trip_legs)
        button.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        # Button to save experiment configuration parameters into a JSON. It'll also check for valid parameters and save them when user requests it
        button = tk.Button(Experiment_screen, text="Save parameters", command=partial(save_parameters, experiment_preset))
        button.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Inform user of expected experiment time before launching experiment
        button = tk.Button(Experiment_screen, text="Estimate experiment timespan", command=estimate_experiment_timespan)
        button.grid(row=0, column=2, padx=10, pady=5, sticky="w")

        # This button launches a scan
        button = tk.Button(Experiment_screen, text="Launch experiment", command=partial(launch_experiment, experiment_data_queue))
        button.grid(row=0, column=3, padx=10, pady=5, sticky="w")

        # Check for errors from thread
        def check_for_errors():
            """Check for errors in the queue and show them in a messagebox."""
            try:
                
                # get_nowait() attempts to immediately get an error from queue
                # but it throws an empty queue error if the queue is empty
                error = error_queue.get_nowait()

                # If the queue is not empty it means we received an error and 
                # the try block will not exit early allowing us to run the following line
                messagebox.showerror("Error", str(error))

                # Continue listening for more future errors
                main_window.after(100, check_for_errors)

            # If we receive no error message we check for errors again after 100ms
            except queue.Empty:
                main_window.after(100, check_for_errors)

        # Start checking for errors
        check_for_errors()


        ################################### Top bar ###################################

        menubar = tk.Menu(main_window)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Initialization screen", command=partial(show_screen_from_menu, "Initialization screen"))
        filemenu.add_command(label="Experiment screen", command=partial(show_screen_from_menu, "Experiment screen"))
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=main_window.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Open Help File", command=open_help_file)
        helpmenu.add_command(label="Open repository", command=open_repository)
        menubar.add_cascade(label="Help", menu=helpmenu)

        main_window.config(menu=menubar)

        # Call the main window to draw the GUI
        main_window.mainloop()


    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")


    # Close up threads
    finally:

        # These variables are initialized as global and None so that
        # we can check whether they have been "filled" and then
        # decide whether to act on them. This way we avoid erros
        if fig is not None:
            plt.close(fig)
        
        if experiment_thread is not None:
            if experiment_thread.is_alive():
                experiment_thread.join()

        if initialization_thread is not None:
            if initialization_thread.is_alive():
                initialization_thread.join()

        if adapter is not None:
            core_logic.close_devices()

        return None


main()
