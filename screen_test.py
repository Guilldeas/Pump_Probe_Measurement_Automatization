import tkinter as tk

import tkinter as tk

def show_screen(screen_name):
    """
    Switch to the selected screen.
    """
    # Hide all frames
    for frame in frames.values():
        frame.pack_forget()
    
    # Show the selected frame
    frames[screen_name].pack(fill="both", expand=True)

# Tkinter setup
root = tk.Tk()
root.title("Multi-Screen GUI")
root.geometry("400x300")

# Create a dictionary to store frames
frames = {}

# Screen 1
frame1 = tk.Frame(root, bg="gray")
frames["Screen 1"] = frame1
label1 = tk.Label(frame1, text="Welcome to Screen 1", font=("Arial", 16))
label1.pack(pady=20)

# Screen 2
frame2 = tk.Frame(root, bg="lightgreen")
frames["Screen 2"] = frame2
label2 = tk.Label(frame2, text="Welcome to Screen 2", font=("Arial", 16))
label2.pack(pady=20)

# Dropdown menu to switch screens
menu_var = tk.StringVar(value="Screen 1")  # Default value
screen_menu = tk.OptionMenu(root, menu_var, *frames.keys(), command=show_screen)
screen_menu.pack(pady=10)

# Show the default screen
show_screen("Screen 1")

root.mainloop()
