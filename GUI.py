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


# TO DO list: From most to least important
#   · Implement a way to save data and safely closing the program
#   · Show graph on screen as experiment takes place (error bars?)
#   · Implement a way to add multiple legs to the trip
#   · Implement a way to change time constant, gain or whatever may affect each leg
#   · Change from mm to fs or whatever
#   · Implement loading different experiment presets, right now there only one, default, and the 
#     user overwrites it to save a preset.
#   · Move functions on GUI.py to their own library



############################### Global variables ###############################
# This boolean flag prevents launching an experiment without
# waiting for the initialization to complete, using a flag 
# allows the user to configure the experiment while the 
# initialization is taking place
initialized = False



def show_screen(screen_name):
    """
    Switch to the selected screen.
    """
    # Hide all frames
    for frame in Screens.values():
        frame.pack_forget()
    
    # Show the selected frame
    Screens[screen_name].pack(fill="both", expand=True)



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
        core_logic.initialization(Troubleshooting=False)
        #core_logic.initialization_dummy(Troubleshooting=False)
    except Exception as e:
        print(f"Error: {e}")  # Will be captured and displayed in GUI
    finally:
        restore_output()



def experiment_thread_logic(start_position, end_position, step_size):
    
    # Catch exceptions while initializing and display them
    # later to user to aid troubleshooting 
    try:
        core_logic.perform_experiment(start_position, end_position, step_size)
        #core_logic.initialization_dummy(Troubleshooting=False)
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
    listbox.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    scrollbar = tk.Scrollbar(waiting_window, orient=tk.VERTICAL)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=listbox.yview)

    # Add a label to inform the user
    label = tk.Label(waiting_window, text="Please wait while the devices are initialized...")
    label.pack(pady=20, padx=20)

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
            button = tk.Button(waiting_window, text="Ok", command=partial(close_window, waiting_window))
            button.pack(side="bottom", padx=20, pady=20)

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



def validate_parameters(default_values, entries_widgets):
    '''
    This funciton gets user values from entries on the screen into a new 
    temporary dict with the same structure as the one holding the 
    default values. It parses them properly and it checks whether the values
    are valid, if they are it will save them on a json, if not it will inform
    the user of the error. 
    '''

    # We construct a dict holding the values input by the user
    # Note: The get method returns all values as strings so we'll 
    # have to parse them later
    screen_values = {}
    for parameter_name, _ in default_values.items():

        # Each entry is read with get from the widgets stored in 
        # the entries dict, this dict was constructed wth the same
        # keys as experiment_preset
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



def save_parameters(default_values, entries_widgets):
    
    valid_parameters, screen_values = validate_parameters(default_values, entries_widgets)
 
    if valid_parameters:

        # Write them into the json
        with open('Utils\experiment_preset.json', "w") as json_file:
            json.dump(screen_values, json_file)
        
            messagebox.showinfo("Parameters saved", f"Parameters were succesfully saved")


    # If any of the parameters is not valid we return
    else:
        return
    


def launch_experiment(default_values, entries_widgets, start_position, end_position, step_size):

    if not initialized:
        messagebox.showinfo("Error launching experiment", "Please wait for device initialization to complete before launching experiment")
        return

    # Verify parameters are safe before launching the experiment
    valid_parameters, screen_values = validate_parameters(default_values, entries_widgets)

    if valid_parameters:

        # Extract correctly parsed and verified parameters into variables
        start_position = screen_values["start_position_mm"]
        end_position = screen_values["end_position_mm"]
        step_size = screen_values["step_size_mm"]

        # Catch exceptions while performing the experiment 
        try:

            # Create a window to monitor experiment
            monitoring_window = Toplevel(main_window)
            monitoring_window.title("Experiment in progress")
            monitoring_window.geometry("800x300")
            monitoring_window.resizable(True, True)
            monitoring_window.grab_set()  # Make it modal (blocks interaction with other windows)

            # Create a Listbox to display initialization messages
            listbox = tk.Listbox(monitoring_window, selectmode=tk.SINGLE, height=15)
            listbox.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            scrollbar = tk.Scrollbar(monitoring_window, orient=tk.VERTICAL)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=listbox.yview)

            # Add a label to inform the user
            label = tk.Label(monitoring_window, text="Please wait while the experiment takes place...")
            label.pack(pady=20, padx=20)

            # Queue for communication between threads
            output_queue = Queue()

            # Redirect stdout and stderr to the queue
            capture_output(output_queue)

            # Run initialization on a different thread
            experiment_thread = threading.Thread(target=experiment_thread_logic, 
                                                 args=(start_position, end_position, step_size))
            experiment_thread.start()

            # Function to check for updates from the queue
            def check_for_updates():
                while not output_queue.empty():
                    new_message = output_queue.get()
                    listbox.insert(tk.END, new_message)
                    listbox.see(tk.END)  # Auto-scroll to the bottom

                if experiment_thread.is_alive():
                    monitoring_window.after(100, check_for_updates)
                else:
                    experiment_thread.join()
                    label.config(text="Initialization Complete")

                    # Add button to close window
                    button = tk.Button(monitoring_window, text="Ok", command=partial(close_window, monitoring_window))
                    button.pack(side="bottom", padx=20, pady=20)

            # Start checking for updates
            #check_for_updates(output_queue, listbox, initialization_thread, waiting_window, label)
            check_for_updates()
            

        except Exception as e:
            print(f"Error: {e}")  # Will be captured and displayed in GUI
    
    else:
        return



def extimate_experiment_timespan(experiment_preset, entries, start_position, end_position, step_size):

    # First get parameters from screen and verify they are valid
    valid_parameters, screen_values = validate_parameters(experiment_preset, entries)

    if valid_parameters:

        start_position = screen_values["start_position_mm"]
        end_position = screen_values["end_position_mm"]
        step_size = screen_values["step_size_mm"]
        estimated_duration = core_logic.request_time_constant(start_position, end_position, step_size)

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
            estimated_duration_mins = int(estimated_duration % (60*60))
            #estimated_duration_secs = int(estimated_duration % 60)

            estimation_message = f"{estimated_duration_hours} hours and {estimated_duration_mins} minutes"
        

        messagebox.showinfo("Estimation", f"Exeriment is estimated to take {estimation_message}")
    
    if not valid_parameters:
        return



def GUI():
    
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
    main_window.geometry("1024x768")

    # There are different screens (dramfes) in this GUI, each serves a different funciton 
    # and must display different frames to change between them we must store them into a
    # dict after building them
    global Screens 
    Screens = {}



    ################################### Initialization Screen #########################
    # We create a frame that will contain everything under this screen, this frame will
    # be shown or hidden depending on what screen we want to display
    Initialization_screen = tk.Frame(main_window)
    Screens["Initialization screen"] = Initialization_screen

    # Add text (label) prompting user to introduce configuration parameters
    label = tk.Label(Initialization_screen, text="Enter device initialization parameters", anchor="w")

    # The widgets will be placed in a grid with respect each other,
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
    delay_parameters_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

    row_num = 0
    label = tk.Label(delay_parameters_frame,  # Instead of placing the widget in the main window we now place it on the frame
                     text="Delay stage parameters",
                     anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    row_num += 1

    
    for parameter, default_value in default_values_delay_stage.items():

        # For every parameter the user will input add a short description with a label 
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
    lockin_parameters_frame.grid(row=2, column=0, padx=10, pady=10, sticky="w")

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
    Screens["Experiment screen"] = Experiment_screen

    # Load experiment configuraiton parameters
    with open('Utils\experiment_preset.json', "r") as json_file:
        experiment_preset = json.load(json_file)

    # TO DO: Allow user to add and configure many legs in the trip

    # Create frame for input parameters
    experiment_parameters_frame = tk.Frame(Experiment_screen)
    experiment_parameters_frame.grid(row=2, column=0, padx=10, pady=10, sticky="w")

    row_num = 0
    label = tk.Label(experiment_parameters_frame, text="Please input experiment parameters", anchor="w")
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
    row_num += 1

    # Add labels and entries following the "default values" json structure
    entries = {} # Store entries for later use
    for parameter, default_value in experiment_preset.items():

        # For every parameter the user will input add a short description with a label 
        label = tk.Label(experiment_parameters_frame, text=parameter, anchor="w")
        label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

        # Add an entry box for the user to write a parameter on the cell and place it to the right
        entry = tk.Entry(experiment_parameters_frame)
        entry.grid(row=row_num, column=1, padx=10, pady=5, sticky="w")

        # Fill entry box with the default value
        entry.insert(0, str(default_value))
        
        # Store entries on a different dict to read their screen values later
        entries[parameter] = entry

        # Following labels and entry boxes will be written a row below
        row_num += 1
    
    # Check for valid parameters and save them when user requests it
    button = tk.Button(Experiment_screen, text="Save parameters", command=partial(save_parameters, experiment_preset, entries))
    button.grid(row=3, column=0, padx=10, pady=5, sticky="w")


    # This button launches a scan
    with open('Utils\experiment_preset.json', "r") as json_file:
        screen_values = json.load(json_file)
    button = tk.Button(Experiment_screen, text="Launch experiment", command=partial(launch_experiment,
                                                                                        experiment_preset, 
                                                                                        entries, 
                                                                                        screen_values["start_position_mm"],
                                                                                        screen_values["end_position_mm"], 
                                                                                        screen_values["step_size_mm"],))
    button.grid(row=3, column=2, padx=10, pady=5, sticky="w")


    # Inform user of expected experiment time before launching experiment
    button = tk.Button(Experiment_screen, text="Estimate experiment timespan", command=partial(extimate_experiment_timespan,
                                                                                        experiment_preset, 
                                                                                        entries, 
                                                                                        screen_values["start_position_mm"],
                                                                                        screen_values["end_position_mm"], 
                                                                                        screen_values["step_size_mm"],))
    button.grid(row=0, column=2, padx=10, pady=5, sticky="w")


    ################################### Top bar ###################################
    # Drop down menu to select different screens
    menu_var = tk.StringVar(value="Initialization screen")  # Default value
    screen_menu = tk.OptionMenu(main_window, menu_var, *Screens.keys(), command=show_screen)
    screen_menu.pack(side="top", anchor="w", padx=0, pady=0)

    # Add a horizontal line (separator) below the dropdown menu
    separator = ttk.Separator(main_window, orient="horizontal")
    separator.pack(fill="x", padx=0, pady=0)  # Fill horizontally, with padding





    # Call the main window to draw the GUI
    show_screen("Initialization screen")    # Run first to show default screen when loading
    main_window.mainloop()






############################### Divide program in threads ###############################
# If we try to run the core logic functions to manage the experiment along the GUI 
# functions we won't be able to do it simultaneously unless we divide them into threads



experiment_thread = threading.Thread(
    target=core_logic.perform_experiment_dummy,
    args=(),
    kwargs={"Troubleshooting": False}
)

GUI_thread = threading.Thread(target=GUI)

# Start the main window thread to draw the GUI
GUI_thread.start()
GUI_thread.join() # I probably have to join this with a close button or something


