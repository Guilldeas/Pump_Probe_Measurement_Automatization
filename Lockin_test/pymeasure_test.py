from pymeasure.adapters import SerialAdapter
import time
import numpy as np
import math



# TO DO
# · Verify whether reference input impedance is 50 or 1Meg 


# --- Initialize Connection ---
def initialize_connection(port="COM5", baudrate=115200, timeout=1):
    """
    Initializes the RS232 connection using PyMeasure's SerialAdapter.
    Returns the initialized adapter.
    """
    try:
        adapter = SerialAdapter(port=port, baudrate=baudrate, timeout=timeout)
        adapter.connection.reset_input_buffer()
        print("RS232 communication initialized successfully with PyMeasure.")
        return adapter
    except Exception as e:
        print(f"Error initializing connection: {e}")
        return None



#------ Configure lockin sensitivity ------
def set_sensitivity(adapter, sensitivity):
    """
    Sets the SR860 sensitivity to the specified value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.
        sensitivity: float - Desired sensitivity value (e.g., 1.0, 500e-3).
    
    Raises:
        ValueError: If the provided sensitivity is not in the predefined list.
    """
    # Sensitivity levels mapped to their indices (from the SR860 manual)
    sensitivity_table = {
        0: 1.0,       1: 500e-3,  2: 200e-3,  3: 100e-3,  4: 50e-3,  5: 20e-3,
        6: 10e-3,     7: 5e-3,    8: 2e-3,    9: 1e-3,   10: 500e-6, 11: 200e-6,
        12: 100e-6,  13: 50e-6,  14: 20e-6,  15: 10e-6,  16: 5e-6,   17: 2e-6,
        18: 1e-6,    19: 500e-9, 20: 200e-9, 21: 100e-9, 22: 50e-9,  23: 20e-9,
        24: 10e-9,   25: 5e-9,   26: 2e-9,   27: 1e-9
    }

    # Find the index for the given sensitivity
    index = None
    for key, value in sensitivity_table.items():
        if abs(value - sensitivity) < 1e-12:  # Compare with tolerance for floats
            index = key
            break

    # If sensitivity not found, raise an error
    if index is None:
        raise ValueError(f"Tried to set sensitivity to invalid value: {sensitivity} V. "
                         f"Valid sensitivities are: {list(sensitivity_table.values())}")

    # Send the SCAL command with the selected index
    try:
        command = f"SCAL {index}\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure the instrument processes the command
        print(f"Sensitivity set to {sensitivity} V (Index {index}).")
    except Exception as e:
        print(f"Error setting sensitivity: {e}")


#------ Configure lockin time constant ------
def set_time_constant(adapter, time_constant):
    """
    Sets the SR860 time constant to the specified value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.
        time_constant: float - Desired time constant value in seconds (e.g., 1e-6 for 1 μs).
    
    Raises:
        ValueError: If the provided time constant is not in the predefined list.
    """
    # Time constant levels mapped to their indices (from the SR860 manual)
    time_constant_table = {
        0: 1e-6,    1: 3e-6,    2: 10e-6,   3: 30e-6,   4: 100e-6,  5: 300e-6,
        6: 1e-3,    7: 3e-3,    8: 10e-3,   9: 30e-3,   10: 100e-3, 11: 300e-3,
        12: 1,      13: 3,      14: 10,     15: 30,     16: 100,    17: 300,
        18: 1e3,    19: 3e3,    20: 10e3,   21: 30e3
    }

    # Find the index for the given time constant
    index = None
    for key, value in time_constant_table.items():
        if abs(value - time_constant) < 1e-12:  # Compare with tolerance for floats
            index = key
            break

    # If time constant not found, raise an error
    if index is None:
        raise ValueError(f"Invalid time constant: {time_constant} s. "
                         f"Valid time constants are: {list(time_constant_table.values())}")

    # Send the OFLT command with the selected index
    try:
        command = f"OFLT {index}\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure the instrument processes the command
        print(f"Time constant set to {time_constant} s (Index {index}).")
    except Exception as e:
        print(f"Error setting time constant: {e}")



# --- Configure Lock-In Communication ---
def configure_lockin(adapter):
    """
    Configures and verifies the SR860 lock-in amplifier communication.
    Example: Clears status, verifies readiness.
    """
    try:
        #------ Clear status registers ------
        adapter.write("*CLS\n")  # Clear status registers
        time.sleep(0.1)
        print("Lock-in amplifier status cleared.")


        #------ Check communication readiness ------
        adapter.write("*IDN?\n")  # Query instrument identification (optional for SR860)
        response = adapter.read().strip()
        if response:
            print(f"Instrument ID: {response}")
        else:
            print("Warning: *IDN? command returned no response. Continuing anyway.")
        

        #------ Configure lockin to measure first harmonic ------
        adapter.write("HARM 1\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("HARM?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print("Configured lockin to read 1st harmonic")
        else:
            print("Unable to configure lockin to read 1st harmonic")


        #------ Configure lockin to external reference ------
        adapter.write("RSRC EXT\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("RSRC?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print("Configured lockin to external reference")
        else:
            print("Unable to configure lockin to external reference")


        #------ Configure lockin to external reference positive TTL ------
        adapter.write("RTRG POSttl\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("RTRG?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 1:
            print("Configured lockin to trigger reference at positive TTL")
        else:
            print("Unable to configure lockin to trigger reference at positive TTL")


        #------ Configure lockin to external reference positive TTL ------
        # NOTE: What input impedance should we configure the reference to? 50 or 1Meg?
        # Lockin is configured to 50 Ohm but let's verify it on owners manual for chopper driver 
        adapter.write("REFZ 50\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("REFZ?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print("Configured lockin to 50 Ohm input reference")
        else:
            print("Unable to configure lockin to 50 Ohm input reference")


        #------ Configure lockin to read a voltage signal ------
        adapter.write("IVMD VOLTAGE\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("IVMD?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print("Configured lockin to read input voltage")
        else:
            print("Unable to configure lockin to read input voltage")


        #------ Configure lockin to read common voltage input ------
        adapter.write("ISRC A\n")
        time.sleep(0.1)

        # Verify it's written succesfuly
        adapter.write("ISRC?\n")
        time.sleep(0.1)
        if int(adapter.read().strip()) == 0:
            print("Configured lockin to read common voltage input")
        else:
            print("Unable to configure lockin to read common voltage input")

        

        
    except Exception as e:
        print(f"Error configuring lock-in amplifier: {e}")



# --- Request signal strength ---
def request_signal_strength(adapter):
    """
    Requests the signal strength indicator which ranges from lowest (0) to overload (4).
    This indicator signifies how much of the ADCs headroom is filled. The input stage of the
    lockin consists on an amplifier that "scales up" the input voltage so that the ADC
    can read it better, however if we scale it up too much the amplifier may give the ADC
    a signal that is too high to read, we call this an "overload", however amplifying too 
    little is not good either since the input noise for the amplifier might be too significant
    compared to the signal level and SNR will suffer. We should always strive to read the highest
    signal level without saturating.
    """
    try:
        command = "ILVL?\n"  # queary signal level
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        return int(response.strip()) # between 0 (lowest) and 4 (overload)
    
    except Exception as e:
        print(f"Error requesting R: {e}")
        return None



# --- Request input amplifier range ---
def request_range(adapter):
    """
    Queries the SR860 for the current voltage input range and returns it as a human-readable value.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.

    Returns:
        str: The voltage range (e.g., "1 V", "300 mV").
    """
    # Range indices mapped to their corresponding voltage ranges
    range_table = {
        0: "1 V",
        1: "300 mV",
        2: "100 mV",
        3: "30 mV",
        4: "10 mV"
    }

    try:
        # Query the current range with IRNG?
        command = "IRNG?\n"
        adapter.write(command)
        time.sleep(0.1)  # Small delay to ensure a response
        response = adapter.read().strip()

        # Convert the response to an integer index
        range_index = int(response)
        if range_index in range_table:
            return f"Current Voltage Range: {range_table[range_index]}"
        else:
            return f"Unexpected range index received: {range_index}"

    except Exception as e:
        print(f"Error requesting voltage range: {e}")
        return None



# --- Request R (Magnitude) ---
def request_R(adapter):
    """
    Requests the R value (magnitude) from the SR860.
    """
    try:
        command = "OUTP? 2\n"  # OUTP? 2 queries R
        adapter.write(command)
        time.sleep(0.1)  # Small delay for processing
        response = adapter.read()
        return float(response.strip()) # in Vrms
    
    except Exception as e:
        print(f"Error requesting R: {e}")
        return None



# --- Request AutoRange ---
def autorange(adapter):
    """
    Sends the command to enable autorange, this sets the input amplifiers gain to fit the signal
    level to the headroom on the subsequent ADC
    """
    try:
        command = "ARNG\n"  # Same result as pressing Auto Range on device
        adapter.write(command)
        time.sleep(0.1)
        '''
        # Always do it twice becuase in the case when the input signal is overloading the amplifier
        # the autorange function will set range to highest 1V, this might be too high for the signal
        # and thus we might loose some headroom 
        command = "ARNG\n"
        adapter.write(command)
        time.sleep(0.1)
        '''

    except Exception as e:
        print(f"Error sending AutoRange command: {e}")


# --- Request Time Constant ---
def request_time_constant(adapter):
    """
    Queries the current time constant setting.
    """

    # List of time constants (in seconds) ordered such that their corresponding index correlates to the index returned by the OFLT? query 
    time_constants = [1E-6, 3E-6, 10E-6, 30E-6, 100E-6, 300E-6, 1E-3, 3E-3, 10E-3, 30E-3, 100E-3, 300E-3, 1, 3, 10, 30, 100, 300, 1E3, 3E3, 10E3, 30E3]

    try:
        command = "OFLT?\n"  # OFLT? queries the time constant index
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read()
        time_constant_index = int(response.strip())  # SR860 returns an index
        return time_constants[time_constant_index]
    
    except Exception as e:
        print(f"Error requesting time constant: {e}")
        return None



# --- Request Filter Slope ---
def request_filter_slope(adapter):
    """
    Queries the current filter slope setting.
    """
    filter_slopes = [6, 12, 18, 24] # In dB/Oct

    try:
        command = "OFSL?\n"  # OFSL? queries the filter slope index
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read()
        filter_slope_index = int(response.strip())  # SR860 returns an index
        return filter_slopes[filter_slope_index]
    
    except Exception as e:
        print(f"Error requesting filter slope: {e}")
        return None



def find_next_sensitivity(adapter):
    """
    Finds and returns the sensitivity value that is right above the current input range.
    
    Parameters:
        adapter: PyMeasure SerialAdapter object for communication.

    Returns:
        float: The next sensitivity value.
    """
    # Input range table (from the IRNG command)
    input_range_table = {
        0: "1 V",
        1: "300 mV",
        2: "100 mV",
        3: "30 mV",
        4: "10 mV"
    }

    # Sensitivity table (from the SCAL command)
    sensitivity_table = {
        0: 1.0,       1: 500e-3,  2: 200e-3,  3: 100e-3,  4: 50e-3,  5: 20e-3,
        6: 10e-3,     7: 5e-3,    8: 2e-3,    9: 1e-3,   10: 500e-6, 11: 200e-6,
        12: 100e-6,  13: 50e-6,  14: 20e-6,  15: 10e-6,  16: 5e-6,   17: 2e-6,
        18: 1e-6,    19: 500e-9, 20: 200e-9, 21: 100e-9, 22: 50e-9,  23: 20e-9,
        24: 10e-9,   25: 5e-9,   26: 2e-9,   27: 1e-9
    }

    try:
        # Step 1: Query the current input range
        command = "IRNG?\n"
        adapter.write(command)
        time.sleep(0.1)
        response = adapter.read().strip()

        current_range_index = int(response)
        if current_range_index not in input_range_table:
            print("Unexpected range index received. Aborting.")
            return None

        current_range = input_range_table[current_range_index]
        print(f"Current Input Range: {current_range} (Index {current_range_index})")

        # Step 2: Find the sensitivity above the current range
        range_voltage_map = {
            "1 V": 1.0,
            "300 mV": 300e-3,
            "100 mV": 100e-3,
            "30 mV": 30e-3,
            "10 mV": 10e-3
        }

        # Get the voltage of the current range
        current_range_value = range_voltage_map[current_range]

        # Find the first sensitivity greater than the current range value
        next_sensitivity = None
        for sensitivity in sorted(sensitivity_table.values()):
            if sensitivity > current_range_value:
                next_sensitivity = sensitivity
                break

        if next_sensitivity:
            print(f"Next Sensitivity: {next_sensitivity} V")
            return next_sensitivity
        else:
            print("No sensitivity found above the current input range.")
            return None

    except Exception as e:
        print(f"Error finding next sensitivity: {e}")
        return None



# --- Close Connection ---
def close_connection(adapter):
    """
    Closes the RS232 connection.
    """
    if adapter and adapter.connection.is_open:
        adapter.connection.close()
        print("Serial port closed successfully.")



# --- Example Usage ---
if __name__ == "__main__":
    # Initialize connection
    adapter = initialize_connection(port="COM5", baudrate=115200, timeout=1)

    if adapter:
        try:
            
            # Configure measurement
            configure_lockin(adapter)

            # Request signal strength
            signal_strength = request_signal_strength(adapter)
            print(f"Signal strength {signal_strength}")

            # Find range automatically
            autorange(adapter)
            print("AutoRange command sent successfully.")

            # Set sensitivity slightly above input range 
            set_sensitivity(adapter, find_next_sensitivity(adapter))

            # Find SNR for this range
            num_measurements = 20
            measurements = []
            for i in range(num_measurements):
                measurements.append(request_R(adapter))

            # The average for our measurements is the DC value at the lockin output
            #  which corresponds to the signal level
            average = sum(measurements)/len(measurements)

            # Anything that is AC is outside of the reference frequency so it's noise
            # noise is calculated then as the standard deviaiton
            variance = sum((x - average) ** 2 for x in measurements) / len(measurements)  # Population standard deviation
            std_dev = math.sqrt(variance)

            print(f"SNR = {(average/std_dev)**2}")

            # Request R (magnitude)
            R_value = request_R(adapter)
            print(f"R: {R_value} Vrms")

            # Request signal strength
            signal_strength = request_signal_strength(adapter)
            print(f"Signal strength {signal_strength}")

            # Request Time Constant
            time_constant = request_time_constant(adapter)
            print(f"Time Constant: {time_constant}s")

            # Set time constant
            set_time_constant(adapter, 10)

            # Request Time Constant
            time_constant = request_time_constant(adapter)
            print(f"Time Constant: {time_constant}s")

            # Request Filter Slope
            filter_slope = request_filter_slope(adapter)
            print(f"Filter Slope: {filter_slope}dB/Oct")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Close connection
            close_connection(adapter)
