from math import floor

for leg in range(0,17):
    print(f"row = {leg%6}, col = {floor(leg/6)}")