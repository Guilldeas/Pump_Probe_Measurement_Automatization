import tkinter as tk
from tkinter import ttk
from tkinter import Toplevel
from tkinter import messagebox
import json
import core_logic
import core_logic_functions as clfun
import threading
import sys
from queue import Queue
from functools import partial
from math import ceil
from tkinter import simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


# TO DO list: From most to least important
#   · Save graph at the end
#   · Specify time zero
#   · Scrollbar for legs list
#   · Save at every point or just at the end option
#
# Less important TO DO list: No order in particular
#   · Safely close program even when experiment is taking place (abort button)
#   · Add boolean flags to experiment that exchange speed for acquracy (measure noise at every step,
#     autogain at every step...)
#   · Choose settling precission or at least verify
#   · Add error bars to saved data
#   · Errors should not fail silently (at east throw an error window)
#   · Define waiting time and number of pulses averaged and store in csv
#   · If OVERLOAD then AUTOGAIN else proceed
#   · Appropiately measure time estimation
#   · Add comment header to CSV
#   · Implement loading different experiment presets, right now there only one, default, and the 
#     user overwrites it to save a preset.
#   · Move functions on GUI.py to their own library



############################### Global variables ###############################
# This boolean flag prevents launching an experiment without
# waiting for the initialization to complete, using a flag 
# allows the user to configure the experiment while the 
# initialization is taking place
initialized = False
entries = {}

# Create a queue object to send data from 
# experiment thread back 
experiment_data_queue = Queue()


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
    def __init__(self, queue):
        self.queue = queue

    def write(self, message):
        if message.strip():  # Avoid empty lines
            self.queue.put(message)

    def flush(self):
        pass  # Required for compatibility



def capture_output(queue):
    """
    Redirect both stdout and stderr to the provided Queue.
    """
    sys.stdout = OutputRedirector(queue)
    sys.stderr = OutputRedirector(queue)  # Capture exceptions



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
        #core_logic.initialization(Troubleshooting=False)
        core_logic.initialization_dummy(Troubleshooting=False)
    except Exception as e:
        print(f"Error: {e}")  # Will be captured and displayed in GUI
    finally:
        restore_output()



def experiment_thread_logic(parameters_dict, experiment_data_queue):
    
    # Catch exceptions while initializing and display them
    # later to user to aid troubleshooting 
    try:
        #core_logic.perform_experiment(parameters_dict, experiment_data_queue)
        core_logic.perform_experiment_dummy(Troubleshooting=False)
    except Exception as e:
        print(f"Error: {e}")  # Will be captured and displayed in GUI
    finally:
        restore_output()
        


def initialize_button():

    # Create the waiting window
    waiting_window = Toplevel(main_window)
    waiting_window.title("Initializing Devices")
    waiting_window.geometry("800x300")
    waiting_window.resizable(True, True)
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
    output_queue = Queue()

    # Redirect stdout and stderr to the queue
    capture_output(output_queue)

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
    all rules or a False whenever one rule is not checked. Additionaly
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
                    messagebox.showinfo("Could not save parameters", f"Parameter {parameter_name} is not a valid floating point number, please use .  as decimal separator")
                    return False, None

        # Other rules specify a range of values
        if rule_type == "max" and parameter_value > rule_value:
            messagebox.showinfo("Could not save parameters", f"Parameter {parameter_name} is above maximum limit: {rule_value}")
            return False, None
        
        if rule_type == "min" and parameter_value < rule_value:
            messagebox.showinfo("Could not save parameters", f"Parameter {parameter_name} is below minimum limit: {rule_value}")
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
    with open('Utils\experiment_preset_validation_rules.json', "r") as json_file:
        validation_rules = json.load(json_file)
    


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
    
    trip_legs = experiment_preset["trip_legs"]

    # We create empty presets to store parameters after validation
    global entries
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
    experiment_preset_save["time_constant"] = entries["time_constant"].get()
    experiment_preset_save["time_zero"] = entries["time_zero"].get()
    experiment_preset_save["trip_legs"] = trip_legs_save
    
    # After all tests have passed we save them into a json
    with open('Utils\experiment_preset.json', "w") as json_file:
    
        json.dump(experiment_preset_save, json_file)
    
        messagebox.showinfo("Parameters saved", f"Parameters were succesfully saved")



def launch_experiment(experiment_data_queue):

    global entries

    if not initialized:
        messagebox.showinfo("Error launching experiment", "Please wait for device initialization to complete before launching experiment")
        return

    # First we'll verify parameters are safe before launching the experiment
    
    # Extract references to data we wanna validate
    Legs_entries = entries["trip_legs"]

    # Construct a dict that will store the parsed verified data to later feed to the delay stage
    experiment_parameters = {
        "experiment_name": entries["experiment_name"].get(), 
        "time_constant": float(entries["time_constant"].get())
        }
    
    trip_legs_parsed = {}

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
        
    # Once parameters are verified and parsed we proceed with the experiment launch

    # Catch exceptions while performing the experiment 
    try:
        # Create a window to monitor experiment
        monitoring_window = Toplevel(main_window)
        monitoring_window.title("Experiment in progress")
        monitoring_window.geometry("1800x600")
        monitoring_window.resizable(True, True)
        monitoring_window.grab_set()  # Make it modal (blocks interaction with other windows)

        # Create scrollable log

        # Create a Listbox to display initialization messages
        listbox = tk.Listbox(monitoring_window, selectmode=tk.SINGLE, height=15)
        scrollbar = tk.Scrollbar(monitoring_window, orient=tk.VERTICAL)

        # Place widgets using grid
        listbox.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Configure scrollbar
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        # Ensure resizing
        monitoring_window.grid_rowconfigure(0, weight=1)
        monitoring_window.grid_columnconfigure(0, weight=1)

        # Add a label to inform the user
        label = tk.Label(monitoring_window, text="Please wait while the experiment takes place...")
        label.grid(padx=20, pady=20)

        # Create live graph

        # Create figure and axes
        fig, axes = plt.subplots()
        axes.set_xlabel('t [ps]')
        axes.set_ylabel('PD [Vrms]')

        # Frame for Graph
        graph_frame = tk.Frame(monitoring_window)
        graph_frame.grid(row=0, column=2, sticky="ew")

        # Canvas for Matplotlib
        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.get_tk_widget().grid(row=0, column=0, sticky="ew")

        # Queue for reading prints from core_logic functions and displaying them on listbox
        output_queue = Queue()

        # Redirect stdout and stderr to the queue
        capture_output(output_queue)

        # Run experiment on a different thread
        experiment_thread = threading.Thread(target=experiment_thread_logic, 
                                                args=(experiment_parameters, experiment_data_queue))
        experiment_thread.start()

        # Function to check for updates from the queue
        def check_for_updates():
            while not output_queue.empty():
                new_message = output_queue.get()
                listbox.insert(tk.END, new_message)
                listbox.see(tk.END)  # Auto-scroll to the bottom

            # Update GUI as long as the experiment is taking place
            if experiment_thread.is_alive():

                # Only update graph whenever new data is acquired
                if not experiment_data_queue.empty():

                    # Get data from thread
                    data_packet = experiment_data_queue.get()
                    positions = data_packet["Positions"]
                    photodiode_data = data_packet["Photodiode data"]
                    photodiode_data_errors = data_packet["Photodiode data errors"]

                    # Clear and re-plot
                    axes.clear()
                    axes.set_xlabel('t [ps]')
                    axes.set_ylabel('PD [Vrms]')
                    axes.plot(positions[:len(photodiode_data)], photodiode_data, marker='o', linestyle='-', color="black")
                    axes.errorbar(positions[:len(photodiode_data)], photodiode_data, yerr=photodiode_data_errors, ecolor="black", fmt='o', linewidth=1, capsize=1)

                    # Fix X-Axis and adjust Y-axis dynamically with some extra space
                    axes.set_xlim(0.9*min(positions), 1.1*max(positions))
                    if len(photodiode_data) > 1:
                        axes.set_ylim(0.5*min(photodiode_data), 1.5*max(photodiode_data))

                    # Redraw Canvas
                    canvas.draw()

                # Check every 100ms for new data
                monitoring_window.after(100, check_for_updates)

            # Close experiment thread after it's done
            else:
                experiment_thread.join()
                label.config(text="Experiment completed")

                # Add button to close window
                button = tk.Button(monitoring_window, text="Ok", command=partial(close_window, monitoring_window))
                button.grid(row=2, column=0, padx=20, pady=20, sticky="s")

        # Start checking for updates
        #check_for_updates(output_queue, listbox, initialization_thread, waiting_window, label)
        check_for_updates()
        

    except Exception as e:
        print(f"Error: {e}")  # Will be captured and displayed in GUI




def estimate_experiment_timespan():

    global entries

    Legs_entries = entries["trip_legs"]
    time_constant = float(entries["time_constant"].get())

    estimated_duration = 0

    # Iterate through dict containing all trip legs
    for leg_entries in Legs_entries.values():

        # For each leg parameters we estimate and accumulate it's duration
        # First get parameters from screen and verify they are valid
        valid_parameters, screen_values = get_parse_validate_screen_params(leg_entries)

        if valid_parameters:

            # Get the relevant parameters
            start_position = screen_values["start [ps]"]
            end_position = screen_values["end [ps]"]
            step_size = screen_values["step [ps]"]

            #time_constant = 1
            settling_time = 5 * time_constant
            average_step_duration_sec = 0.5 + settling_time
            num_steps = ceil( (end_position - start_position) / step_size )

            estimated_duration += int(average_step_duration_sec * num_steps )
        
        if not valid_parameters:
            return


    # At the end of the estimation we create a message for the user
    estimation_message = ""

    # When estimated duration is below 1 min we give an estimation in seconds
    # to make it more readable
    if estimated_duration < 60:
        estimation_message = str(estimated_duration) + " seconds"

    # Readability for experiments below an hour
    elif estimated_duration < 60*60:
        estimated_duration_mins = int(estimated_duration / 60)
        estimated_duration_secs = int(estimated_duration % 60)

        estimation_message = f"{estimated_duration_mins} minutes and {estimated_duration_secs} seconds"

    # Experiments below a day
    elif estimated_duration < 60*60*24:
        estimated_duration_hours = int(estimated_duration / (60*60))
        estimated_duration_mins = int((estimated_duration % (60*60))/60)

        estimation_message = f"{estimated_duration_hours} hours and {estimated_duration_mins} minutes"
    
    # Experiments above
    elif estimated_duration >= 60*60*24:
        estimated_duration_days = int(estimated_duration / (60*60*24))

        estimation_message = f"above {estimated_duration_days} days... Don't you think you are pushing it just a little?"
    
    
    

    messagebox.showinfo("Estimation", f"Experiment is estimated to take {estimation_message}")



def create_experiment_gui_from_dict(parameters_dict):

    experiment_name = parameters_dict["experiment_name"]
    time_constant = parameters_dict["time_constant"]
    time_zero = parameters_dict["time_zero"]
    trip_legs = parameters_dict["trip_legs"]

    experiment_parameters_frame = Screens["Experiment screen"]["Child frame"]

    # Erase previous screen
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
    label = tk.Label(experiment_parameters_frame, text="experiment file name", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(experiment_parameters_frame)
    entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entry.insert(0, experiment_name)
    entries["experiment_name"] = entry
    row_num += 1

    # time constant can only be a series of values
    time_constant_table = [1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1e3, 3e3, 10e3, 30e3]

    # Create Combobox to select time constant from
    label = tk.Label(experiment_parameters_frame, text="time constant [s]", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    combo = ttk.Combobox(experiment_parameters_frame, values=time_constant_table, state="readonly")
    combo.set(time_constant)  # Default value
    combo.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entries["time_constant"] = combo
    row_num += 1

    # Time zero input
    label = tk.Label(experiment_parameters_frame, text="time zero [ps]", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(experiment_parameters_frame)
    entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")
    entry.insert(0, time_zero)
    entries["time_zero"] = entry
    row_num += 1


    trip_legs_entries = {}
    # trip_legs is a dict storing each leg with it's corresponding parameters
    for leg_number, leg_parameters in trip_legs.items():

        # For starters we keep the parameters for each leg into their own buffer dict
        trip_leg_entry = {}

        # Label at the start the number for the leg
        label = tk.Label(experiment_parameters_frame, text=f"leg number {leg_number}", anchor="w")
        label.grid(row=row_num, column=0, padx=10, pady=15, sticky="w")
        row_num += 1

        # For each leg parameters we iteratively write them on screen
        for parameter, default_value in leg_parameters.items():

            # For every parameter the user will input add a short description with a label 
            label = tk.Label(experiment_parameters_frame, text=parameter, anchor="w")
            label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

            # Add an entry box for the user to write a parameter on the cell and place it to the right
            entry = tk.Entry(experiment_parameters_frame)
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

    global entries

    # We first ask the user to input number of legs in the trip
    num_legs = int(simpledialog.askstring("Input", "Please enter number of legs in the trip:"))

    # We then construct a dict from which to construct the GUI later holding placeholder values
    # but we should still preserve parameters that the user might care for
    time_constant = float(entries["time_constant"].get())
    time_zero = float(entries["time_zero"].get())
    new_experiment_dict = {"experiment_name": "new_experiment", "time_constant": str(time_constant), "time_zero": str(time_zero)}
    
    # We now append as many trip legs as requested
    new_legs = {}
    for leg_number in range(0, num_legs):
        new_legs[str(leg_number)] = {"start [ps]": 0.0, "end [ps]": 0.0, "step [ps]": 0.0}

    new_experiment_dict["trip_legs"] = new_legs

    # And proceed to construct a new frame with the placeholder data, passing these arguments deletes
    # the previously drawn frame Entries_Frame, experiment_preset
    create_experiment_gui_from_dict(new_experiment_dict)



############################### MAIN code starts here ###########################

# Extract default configuration values for both devices from the configuration file
with open('Utils\default_config.json', "r") as json_file:
    default_config = json.load(json_file)

default_values_delay_stage = default_config["Delay Stage Default Config Params"]
default_values_lockin = default_config["Lockin Default Config Params"]



############################### Start drawing GUI ###############################
# Create the main window
global main_window
main_window = tk.Tk()
main_window.title("Automatic Pump Probe")
main_window.geometry("1920x1080")

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

Initialization_screen.grid(row=2, column=0, padx=10, pady=10)#, sticky="ew")
third_label = tk.Label(Initialization_screen, text="Third row label Child", anchor="w")
third_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
    

Screens["Initialization screen"] = {}
Screens["Initialization screen"]["Screen frame"] = Initialization_screen
Screens["Initialization screen"]["Child frame"] = None


# Add text (label) prompting user to introduce configuration parameters
label = tk.Label(Initialization_screen, text="Enter device initialization parameters", anchor="w")
label.grid(row=0, column=0, padx=10, pady=5)#, sticky="w")

# The widgets will be placed in a grid with respect to each other,
# to define their separation we define a "no place" x and y pad radius measured 10px around them
# finally we specify "w" to format them to the left or west of their "cell"
row_num = 0
label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

# Place an empty label at the end to add some space
spacer = tk.Label(Initialization_screen, text="")  # An empty label
spacer.grid(row=row_num, column=0, pady=10)  # Adds vertical space
row_num += 1



############################### Frame for delay stage ###############################
# To create a section we use a frame which we will treat code wise as a window in which 
# to place our widgets, this has the added benefit of referencing these widgets on a new subgrid, 
# it's more modular too since we can rearrange the whole frame without loosing the reference
# between widgets  

# We place the frame indexing it to the initialization screen frame
delay_parameters_frame = tk.Frame(Initialization_screen)
delay_parameters_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

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
lockin_parameters_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

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
button = tk.Button(Initialization_screen, text="Initialize devices", command=initialize_button)
button.grid(row=3, column=0, padx=10, pady=5, sticky="w")




################################### Experiment Configuration Screen #########################
# This screen holds the parameters to configure the experiment and visualize it
Experiment_screen = tk.Frame(main_window)
Screens["Experiment screen"] = {}
Screens["Experiment screen"]["Screen frame"] = Experiment_screen

# Load experiment configuration parameters
with open('Utils\experiment_preset.json', "r") as json_file:
    experiment_preset = json.load(json_file)

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



################################### Top bar ###################################    
# Drop down menu to select different screens
menu_var = tk.StringVar(value="Initialization screen")  # Default value
screen_menu = tk.OptionMenu(main_window, menu_var, *Screens.keys(), command=show_screen_from_menu)
screen_menu.grid(row=0, column=0, padx=0, pady=0, sticky="w")

# Add a horizontal line (separator) below the dropdown menu
separator = ttk.Separator(main_window, orient="horizontal")
separator.grid(row=1, column=0, padx=0, pady=0, sticky="ew")  # Fill horizontally, with padding

# Run first to show default screen when loading
show_screen(screen_name="Initialization screen", frame_type="Screen frame")

# Ensure row 0 and row 1 stay fixed
main_window.grid_rowconfigure(0, weight=0)
main_window.grid_rowconfigure(1, weight=0)

# Ensure row 2 (Initialization_screen) expands properly
main_window.grid_rowconfigure(2, weight=0)
main_window.grid_columnconfigure(0, weight=1)  # Allow width expansion

# Call the main window to draw the GUI
main_window.mainloop()
