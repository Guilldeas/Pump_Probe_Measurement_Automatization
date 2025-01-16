import sys

def capture_stdout():
    """
    Redirects stdout and captures printed text into an array.
    """
    captured_output = []  # Array to store the printed text

    class OutputRedirector:
        def write(self, message):
            captured_output.append(message)

        def flush(self):
            pass  # Required for compatibility

    # Redirect stdout to the custom OutputRedirector
    sys.stdout = OutputRedirector()

    return captured_output

# Example usage
if __name__ == "__main__":
    # Redirect stdout
    captured_output = capture_stdout()

    # Print some messages (these are captured into the array)
    print("Hello, world!")
    print("This is stored in an array.")

    # Restore stdout to its original state
    sys.stdout = sys.__stdout__

    # Print the captured output array
    print("Captured Output Array:", captured_output)
