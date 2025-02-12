import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import *
import numpy as np
import threading
import time
from random import uniform
import queue


# Create a queue object to send data from 
# experiment thread back 
experiment_data_queue = queue.Queue()

# Tkinter Window (MUST be in the main thread)
graph_window = Tk()
graph_window.title("Live Data")
graph_window.geometry("800x600")


# Create figure and axes
fig, axes = plt.subplots()
axes.set_xlabel('t [ps]')
axes.set_ylabel('PD [Vrms]')

# Frame for Graph
graph_frame = Frame(graph_window)
graph_frame.pack()

# Canvas for Matplotlib
canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas.get_tk_widget().pack()


# Function to update the plot dynamically
def update_plot():

    # Only update the GUI when new data is received from the experiment thread
    if not experiment_data_queue.empty():

        # Get data from thread
        data_packet = experiment_data_queue.get()
        positions = data_packet["Positions"]
        photodiode_data = data_packet["Photodiode data"]
        photodiode_data_errors = data_packet["Photodiode data errors"]

        # Clear and re-plot
        axes.clear()
        axes.plot(positions[:len(photodiode_data)], photodiode_data, marker='o', linestyle='-', color="black")
        axes.errorbar(positions[:len(photodiode_data)], photodiode_data, yerr=photodiode_data_errors, ecolor="black", fmt='o', linewidth=1, capsize=1)


        # Adjust Y-axis dynamically
        axes.set_xlim(min(positions), max(positions))
        if len(photodiode_data) > 1:
            axes.set_ylim(min(photodiode_data) - 0.1, max(photodiode_data) + 0.1)

        # Redraw Canvas
        canvas.draw()

    # This is a way to avoid freezing the GUI while waiting in the while loop for new data.
    # We call this function after 100ms
    graph_window.after(100, update_plot)  # Run again in 100ms


# Function to simulate data acquisition (Runs in a separate thread)
def dummy_perform_experiment():

    Positions = []
    Photodiode_data = []
    Photodiode_data_errors = []

    # Build fake scan positions
    for position in range(0, 100):
        Positions.append(position)

    # Simulate data acquisition
    for index in range(0, 100):

        Photodiode_data.append(np.sin(Positions[index] / 2))
        time.sleep(1)  # Simulate delay

        Photodiode_data_errors.append(uniform(0, 1))
        time.sleep(1)  # Simulate delay

        # Send data through queue to GUI to draw it. Do it with copies or else
        # we'll pass references to the local lists "Photodiode_data" and the GUI will
        # be able to access them and attempt to draw from them, this leads to an error
        # where the error bar has not been calculated but the photodiode data has been
        # acquired leading to an incorrect size error when plotting 
        data_packet = {
                        "Photodiode data": Photodiode_data.copy(), 
                        "Photodiode data errors": Photodiode_data_errors.copy(),
                        "Positions": Positions.copy()
                      }
        experiment_data_queue.put(data_packet)

    print("Experiment complete!")


# Start the experiment in a separate thread
experiment_thread = threading.Thread(target=dummy_perform_experiment, daemon=True)
experiment_thread.start()


# Start updating the plot
update_plot()

# Tkinter mainloop (MUST stay in the main thread)
graph_window.mainloop()
