def func_b():
    int_a = 3
    str_b = 'Hello'

    try:
        result = int_a + str_b
    except Exception as e:
        #print(f"An undetermined error occured when adding:\n{e}")
        raise Exception(f"An undetermined error occured when adding:\n{e}")