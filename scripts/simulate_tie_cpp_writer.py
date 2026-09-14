#!/usr/bin/env python3
import os
import sys

def main():
    N_F = 32
    M_MAX = 3
    data_dir = "Player-Data"
    os.makedirs(data_dir, exist_ok=True)
    
    path0 = os.path.join(data_dir, "Input-P0-0")
    path1 = os.path.join(data_dir, "Input-P1-0")
    
    with open(path0, "w") as f0, open(path1, "w") as f1:
        # A_scores: Set to constant 10
        for i in range(N_F):
            f0.write("10\n")
            f1.write("0\n")
        # A_valid: First 15 are valid
        for i in range(N_F):
            valid = 1 if i < 15 else 0
            f0.write(f"{valid}\n")
            f1.write("0\n")

        # CPSI slots
        for b in range(N_F):
            # All valid items match on slot 0 with score 100
            match = 1 if b < 15 else 0
            
            for m in range(M_MAX):
                if m == 0 and match:
                    f0.write("1\n"); f1.write("0\n") # flag
                    f0.write("100\n"); f1.write("0\n") # score
                else:
                    f0.write("0\n"); f1.write("0\n")
                    f0.write("0\n"); f1.write("0\n")
                    
            # Overflow share
            f0.write("0\n")
            f1.write("0\n")
            
    print(f"Wrote exact tie shares to {path0} and {path1}")

if __name__ == "__main__":
    main()
