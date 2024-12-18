from srsinst.sr860 import SR860

# only required for USB or GPIB communication
import pyvisa as visa 
import math
import serial
import time
from pymeasure.adapters import SerialAdapter

num_averages = 10

#################### PyMeasure Implementation ####################
# Initialize Serial Communication with PyMeasure
try:
    adapter = SerialAdapter(port="COM5", baudrate=115200, timeout=0.5)  # Reduced timeout
    adapter.connection.reset_input_buffer()
    print("RS232 communication initialized successfully with PyMeasure.\n")

    # Send Command to Retrieve R (Magnitude)
    command = "OUTP? 2\n"  # Query R value with \n terminator
    print(f"Sending command: {command.strip()}")
    
    start_time = time.time()  # Start profiling
    adapter.write(command)  # Send command
    
    # Read Response - Break out of read loop as soon as data is available
    response = ""
    while True:
        if adapter.connection.in_waiting > 0:
            response += adapter.read()  # Non-blocking read
            break  # Stop as soon as data is read
        if time.time() - start_time > 1:  # Safety timeout
            print("Timeout: No response received.")
            break

    elapsed_time = time.time() - start_time
    print(f"PyMeasure Optimized Response: {response.strip()} in {elapsed_time:.6f}s")

except Exception as e:
    print(f"Error communicating with SR860: {e}")

finally:
    if adapter.connection.is_open:
        adapter.connection.close()
        print("\nSerial port closed.")





#################### Serial Implementation ####################
try:
    # Open the serial port (update 'COM5' if your port is different)
    ser = serial.Serial(
        port='COM5',          # Replace with your port
        baudrate=115200,      # Baud rate from SR860 manual
        bytesize=8,           # Data bits
        parity='N',           # No parity
        stopbits=1,           # 1 stop bit
        timeout=12             # Timeout for reading (in seconds)
    )
    print("RS232 communication initialized successfully.\n")

except Exception as e:
    print(f"Error initializing communication: {e}")

    # Exit makes it so that nothing will be executed after exiting the failed try block
    exit()

# --- Send Command to Retrieve R ---
try:
    start_time = time.time()
    command = "OUTP? 2\n"
    print(f"Sending command: {command.strip()}")
    ser.write(command.encode())  # Encode the command as bytes and send it

    # --- Wait for Response ---
    response = ""
    start_time = time.time()
    while True:
        if ser.in_waiting > 0:  # Check if data is available to read
            response += ser.read(ser.in_waiting).decode('utf-8')  # Read available data
            if "\n" in response or "\r" in response:  # Check for end of message
                break
        if time.time() - start_time > 12:  # Break if response takes too long
            print("Timeout: No response received from SR860.")
            break

    # --- Display Response ---
    if response:
        end_time = time.time()
        print(f"Serial implementation received response: {response.strip()} in {end_time-start_time}s")  # Print the response


    else:
        print("No response received.")

except Exception as e:
    print(f"Error communicating with SR860: {e}")

finally:
    # --- Close the Serial Port ---
    if ser.is_open:
        ser.close()
        print("\nSerial port closed.")



#################### SRS Module Implementation ####################
lockin_USB_port = 'COM5'
lockin = SR860()

try:
    lockin.connect('serial', lockin_USB_port)
    start_time = time.time()
    R_value = lockin.data.value['R']
    end_time = time.time()
    print(f"SRS implementation received response: {R_value} in {end_time-start_time}s")  # Print the response



except Exception as e:
    print(e)

