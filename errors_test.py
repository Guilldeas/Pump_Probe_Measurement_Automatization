import errors_test_lib as et_lib
import queue
import threading
import tkinter as tk
from tkinter import messagebox


error_queue = queue.Queue()
initialization_thread = None

def initialization_thread_logic():
    try:
        # Create and start thread
        global initialization_thread
        initialization_thread = threading.Thread(target=et_lib.func_b())
        initialization_thread.start()

    # Catch raised exception on imported function and send it to main() from thread with queue
    except Exception as e:
        error_queue.put(Exception(f"An error occured when initializing in function et_lib.func_b():\n{e}"))
    
    finally:
        initialization_thread.join()


def main():

    # Create GUI
    root = tk.Tk()
    root.title("Basic Tkinter Window")

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

            # Continue listening for more errors
            root.after(100, check_for_errors)

        # If we receive no error message we check for errors again after 100ms
        except queue.Empty:
            root.after(100, check_for_errors)

    check_for_errors()

    button = tk.Button(root, text="Force Error", command=initialization_thread_logic)
    button.grid(padx=10, pady=5, sticky="w")


    # Run the Tkinter event loop
    root.mainloop()
    

try:
    main()

# If an error somehow propagates all the way up we still fisplay it on a messagebox
except Exception as e:
    messagebox.showerror("Error", str(e))

finally:
    initialization_thread.join()

