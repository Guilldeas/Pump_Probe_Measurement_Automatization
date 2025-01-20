import tkinter as tk
from tkinter import ttk
from tkinter import Toplevel
import json
import core_logic
import threading
import sys
from queue import Queue
from functools import partial



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

def initialize_button():
    def initialization_thread_logic():
        
        # Catch exceptions while initializing and display them
        # later to user to aid troubleshooting 
        try:
            core_logic.initialization(Troubleshooting=False)
        except Exception as e:
            print(f"Error: {e}")  # Will be captured and displayed in GUI
        finally:
            restore_output()

    # Create the waiting window
    waiting_window = Toplevel(main_window)
    waiting_window.title("Initializing Devices")
    waiting_window.geometry("800x300")
    waiting_window.resizable(True, True)
    waiting_window.grab_set()  # Make it modal (blocks interaction with other windows)

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

            # Add button to close window
            button = tk.Button(waiting_window, text="Ok", command=partial(close_window, waiting_window))
            button.pack(side="bottom", padx=20, pady=20)

    # Start checking for updates
    check_for_updates()




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

    # Add labels in succession
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



    ################################### Experiment Screen #########################
    # This screen holds the parameters to configure the experiment and visualize it
    Experiment_screen = tk.Frame(main_window)
    Screens["Experiment screen"] = Experiment_screen

    label = tk.Label(Experiment_screen, text="Enter device experiment parameters", anchor="w")
    row_num = 0
    label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

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
GUI_thread.join()
#experiment_thread.join()



'''
# Add a button
def on_submit():
    user_input = entry.get()
    label.config(text=f"You entered: {user_input}")

button = tk.Button(main_window, text="Submit", command=on_submit)
button.grid(row=3, column=0, padx=10, pady=5, sticky="w")
'''

