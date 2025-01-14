import tkinter as tk

# Fakey fake params in main code. A dict holds both the parameters name and it's default value
# perhaps store them in a CSV and retreive from it at the start? 
default_values_delay_stage = {
    "Serial number:": "103391384",
    "Channel:": 1,
    "Acceleration[mm/s^2]:": 900.0,
    "Max velocity[mm/s]:": 45.0
}
default_values_lockin = {
    "USB port:" : "COM5",
    "Baud rate" : 115200
}

# Create the main window
root = tk.Tk()
root.title("User Input Example")
root.geometry("400x300")

# Add text (label) prompting user to introduce configuration parameters
label = tk.Label(root, text="Enter device initialization parameters", anchor="w")

# The widgets will be placed in a grid with respect each other,
#  to define their separation we define a "no place" x and y pad radius measured 10px around them
# finally we specify to format them to the left or west of their "cell"
row_num = 0
label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

# Place an empty label at the end to add some space
spacer = tk.Label(root, text="")  # An empty label
spacer.grid(row=row_num, column=0, pady=10)  # Adds vertical space
row_num += 1



############################### Section for delay stage ###############################
# To create a section we use a frame which we will treat code wise as a window  in which 
# to place our widgets, this has the added benefit of referencing these widgets on a new subgrid, 
# it's more modular too since we can rearrange the whole frame without loosing the reference 
delay_parameters_frame = tk.Frame(root)

# We place the frame indexing it to the main window grid
delay_parameters_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

# Instead of placing it in the main window we place it on the frame
row_num = 0
label = tk.Label(delay_parameters_frame, text="Delay stage parameters", anchor="w")
label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
row_num += 1

# Add labels in succession
delay_stage_input_parameters = ["Serial number:", "Channel:", "Acceleration[mm/s^2]:", "Max veocity[mm/s]"]
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




############################### Section for delay stage ###############################
# Repeat for lockin parameters
lockin_parameters_frame = tk.Frame(root)
lockin_parameters_frame.grid(row=2, column=0, padx=10, pady=10, sticky="w")

row_num = 0
label = tk.Label(lockin_parameters_frame, text="Lock-in parameters", anchor="w")
label.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")
row_num += 1

# Add labels in succession
lockin_input_parameters = ["USB port:", "Baud Rate:"]
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




'''
# Add a button
def on_submit():
    user_input = entry.get()
    label.config(text=f"You entered: {user_input}")

button = tk.Button(root, text="Submit", command=on_submit)
button.grid(row=3, column=0, padx=10, pady=5, sticky="w")
'''
# Run the main loop
root.mainloop()
