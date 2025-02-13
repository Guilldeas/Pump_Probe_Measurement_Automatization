import numpy as np

Positions = [0, 10, 20, 30, 45]
time_zero = 10

Positions_relative = []
for position in Positions:
    Positions_relative.append(position - time_zero)

print(Positions_relative)
