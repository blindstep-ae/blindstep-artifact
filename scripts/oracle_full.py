#!/usr/bin/env python3
"""
Oracle for BlindStep WP4 Full Primitive Validation
"""
import sys
import math

N_MAX = 128
K_DEFAULT = 5

def tuple_key(candidate):
    return (candidate[0], candidate[1], -candidate[2])

def mock_module1_candidate_table():
    candidates = []
    for i in range(N_MAX):
        if 5 <= i <= 15:
            valid = 1
            score_a = i * 2
            score_b = i * 3
            score = score_a + score_b
            tie = i
            candidates.append((valid, score, tie))
        else:
            candidates.append((0, 0, i))
    return candidates

def module2_top_k(candidates, k):
    dummy_inits = [(0, 0, 0) for _ in range(k)]
    all_elements = candidates + dummy_inits
    all_elements.sort(key=tuple_key, reverse=True)
    return all_elements[:k]

def main():
    candidates = mock_module1_candidate_table()
    top_k = module2_top_k(candidates, K_DEFAULT)
    
    for rank, (valid, score, tie) in enumerate(top_k):
        # CSV format matches compare_module2_results.py format
        print(f"CSV,{rank},{valid},{score}")

if __name__ == "__main__":
    main()
