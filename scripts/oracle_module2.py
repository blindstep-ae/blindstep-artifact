#!/usr/bin/env python3
"""
# Oracle for BlindStep Module 2 (Secure Insertion Queue)
#
# Constraints & Specifications:
# - Tuple: τ = (valid, score, tie)
# - Sort Key: (valid, score, -tie) descending
# - Dummy semantics: τ_⊥ = (0, 0, 0)
"""

import sys

N_MAX = 128
K_DEFAULT = 5

def tuple_key(candidate):
    """
    Returns the sort key based on frozen spec priority:
    (valid, score, -tie)
    """
    valid, score, tie = candidate
    return (valid, score, -tie)

def top_k_plaintext(candidates, k):
    """
    Mock implementation of the Module 2 MP-SPDZ Secure Insertion Queue.
    In the MPC queue, the buffer is initialized with dummy τ_⊥ = (0, 0, 0).
    Here, we append K dummy values to candidates and return the Top K 
    based on the exact tuple_key mapping.
    """
    dummy_inits = [(0, 0, 0) for _ in range(k)]
    all_elements = candidates + dummy_inits
    
    # Sort descending
    all_elements.sort(key=tuple_key, reverse=True)
    
    return all_elements[:k]

def print_top_k(name, top_k):
    """
    Formats the output array exactly as required:
    1. Human-Readable
    2. Machine-Readable (CSV)
    """
    print(f"\n--- {name} ---")
    for rank, (valid, score, tie) in enumerate(top_k):
        print(f"Rank {rank}: Valid={valid}, Score={score}")
        print(f"CSV,{rank},{valid},{score}")

def test_a_monotonic():
    candidates = []
    for i in range(N_MAX):
        if i < 10:
            candidates.append((1, i * 10, i))
        else:
            candidates.append((0, 0, i))

    top_k = top_k_plaintext(candidates, K_DEFAULT)
    print_top_k("Test A: Monotonic Scores", top_k)
    
    expected_scores = [90, 80, 70, 60, 50]
    expected = [(1, s, s // 10) for s in expected_scores]
    
    if top_k == expected:
        print("Test A: ✅ PASS")
    else:
        print("Test A: ❌ FAIL")

def test_b_all_invalid():
    candidates = [(0, 0, i) for i in range(N_MAX)]
    
    top_k = top_k_plaintext(candidates, K_DEFAULT)
    print_top_k("Test B: All Invalid", top_k)
    
    expected = [(0, 0, 0) for _ in range(K_DEFAULT)]
    
    if top_k == expected:
        print("Test B: ✅ PASS")
    else:
        print("Test B: ❌ FAIL")

def test_c_tie_breaking():
    candidates = []
    for i in range(N_MAX):
        if i < 10:
            candidates.append((1, 100, i)) # All score=100
        else:
            candidates.append((0, 0, i))
            
    top_k = top_k_plaintext(candidates, K_DEFAULT)
    print_top_k("Test C: Tie Breaking (Score=100 for all valid)", top_k)
    
    # tie is smallest-first, so i=0, 1, 2, 3, 4 should be selected
    expected = [(1, 100, i) for i in range(K_DEFAULT)]
    
    if top_k == expected:
        print("Test C: ✅ PASS")
    else:
        print("Test C: ❌ FAIL")

def test_d_boundary_k_strict():
    # 构造具有明确梯度的数据集
    # i < 15: Valid=1, Score=i*10, Tie=i
    # i >= 15: Valid=0, Score=0, Tie=i
    candidates = [(1, i*10, i) if i < 15 else (0, 0, i) for i in range(N_MAX)]
    
    overall_pass = True
    # 测试不同的 K，确保截断点和排序完全符合预期
    for k in [1, 5, 10, 20]:
        top_k = top_k_plaintext(candidates, k)
        
        # 构造预期的全量排序序列
        # 1. 有效值部分：Score 越高越靠前，即 i 越大越靠前 (14, 13, ..., 0)
        # 2. 填充部分：如果 k > 15，剩余部分应为 (0, 0, 0) 哨兵
        full_expected_sorted = [(1, i*10, i) for i in range(14, -1, -1)] + \
                               [(0, 0, 0) for _ in range(max(0, k - 15))]
        expected = full_expected_sorted[:k]
        
        print_top_k(f"Test D Strict: Boundary K={k}", top_k)
        
        if top_k == expected:
            print(f"Test D (K={k}): ✅ PASS (Content Verified)")
        else:
            print(f"Test D (K={k}): ❌ FAIL (Content Mismatch!)")
            print(f"  Expected first element: {expected[0] if expected else 'None'}")
            print(f"  Actual first element:   {top_k[0] if top_k else 'None'}")
            overall_pass = False
            
    if overall_pass:
        print("Test D Overall: ✅ PASS (Strictly Verified)")

def test_e_exact_k_valid():
    candidates = [(1, i*10, i) if i < K_DEFAULT else (0, 0, i) for i in range(N_MAX)]
    
    top_k = top_k_plaintext(candidates, K_DEFAULT)
    print_top_k("Test E: Exact K Valid", top_k)
    
    # i goes from 0..4 (scores 0..40). High to low -> (1, 40, 4) down to (1, 0, 0)
    expected = [(1, i*10, i) for i in reversed(range(K_DEFAULT))]
    
    if top_k == expected:
        print("Test E: ✅ PASS")
    else:
        print("Test E: ❌ FAIL")

def test_f_less_than_k_valid():
    num_valid = 3
    candidates = [(1, i*10, i) if i < num_valid else (0, 0, i) for i in range(N_MAX)]
    
    top_k = top_k_plaintext(candidates, K_DEFAULT)
    print_top_k("Test F: Less than K Valid", top_k)
    
    # i goes from 0..2 (scores 0..20)
    valid_expected = [(1, i*10, i) for i in reversed(range(num_valid))]
    dummy_expected = [(0, 0, 0) for _ in range(K_DEFAULT - num_valid)]
    expected = valid_expected + dummy_expected
    
    if top_k == expected:
        print("Test F: ✅ PASS")
    else:
        print("Test F: ❌ FAIL")

def main():
    print("====================================")
    print("BlindStep Module 2 - Plaintext Oracle")
    print("====================================")
    
    test_a_monotonic()
    test_b_all_invalid()
    test_c_tie_breaking()
    test_d_boundary_k_strict()
    test_e_exact_k_valid()
    test_f_less_than_k_valid()

if __name__ == "__main__":
    main()
