import random
import numpy as np



def average_scans(Completed_scans, new_data):
    # We want to measure a live average, that is we need to update 
    # each averaged point in a graph as new points come in, to do so
    # we use this function which averages multiple lists and deals
    # with problems where the last scan is incomplete and thus a smaller
    # length, to do so it splits the averaging like so:
    #  
    # We slice completed scans by the len of the uncompleted scan
    # [a_0, a_1| a_2, a_3, a_4, a_5]
    # [b_0, b_1| b_2, b_3, b_4, b_5]
    #
    # Current scan taking place that is incomplete
    # [c_0, c_1]
    #
    # average left slices: [a_0, a_1], [b_0, b_1], [c_0, c_1]
    # average right slices: [a_2, a_3, a_4, a_5], [b_2, b_3, b_4, b_5]]
    #
    # We splice left and right averages into a final average
    # [avg_0, avg_1, avg_2, avg_3, avg_4, avg_5]


    def average_equal_lists(scans_list):
        # Takes a list of equal sized lists and returns an 
        # averaged list

        # Cast lists to arrays for easier element wise addition
        scans_array_list = []
        for scan in scans_list:
            scans_array_list.append(np.array(scan))
        
        # Average all scan arrays in list by summing them
        averaged_scans = np.zeros_like(np.array(scans_array_list[0]))
        for scan in scans_array_list:
            averaged_scans += scan
        
        # And dividing by amount of arrays
        averaged_scans = averaged_scans / len(scans_array_list)
        
        return averaged_scans.tolist()

    # Append new data to completed scans
    Scans = Completed_scans
    Scans.append(new_data)

    # Deal with edge case where there are not enough scans to average
    if len(Scans) > 1:

        # Find whether our averaging needs to deal with incompleted scans
        # by checkin whether the last scan is smaller than the previous one  
        if len(Scans[-1]) == len(Scans[-2]):
            return average_equal_lists(Scans)

        else:

            # Compile list of scans sliced to match the length of the 
            # uncompleted scan
            left_slices_list = []
            for scan in Scans[:-1]:
                left_slices_list.append(scan[:len(Scans[-1])])
            
            # Include uncomplete scan
            left_slices_list.append(Scans[-1])
            
            # Compile a second list of the "leftover" right slices
            right_slices_list = []
            for scan in Scans[:-1]:
                right_slices_list.append(scan[len(Scans[-1]):])
            
            #print(f'Scans: {Scans}')
            #print(f'left slices: {left_slices_list}\n right slices: {right_slices_list}')

            # Average each of the groups, now with matching length
            left_average = average_equal_lists(left_slices_list)
            right_average = average_equal_lists(right_slices_list)

            # Combine them into a final average
            return left_average + right_average

    # This return signals that there is no average to plot for only
    # one scan
    else:
        return None



### Simulate data

# Generate 4 sets of data for 4 complete scans
Completed_scans = []

scan_len = 5
for scan in range(0, 1):
    Completed_scans.append(random.sample(range(-50, 50), scan_len))


# Append one final scan in process
scan_len = 3
new_data = random.sample(range(-50, 50), scan_len)


print(average_scans(Completed_scans, new_data))
