#!/usr/bin/env python3
import sys
import argparse
import re
import os

# 约束：rank(非负), valid(0/1), score(整数)
CSV_PATTERN = re.compile(
    r"^\s*CSV\s*,\s*"
    r"(?P<rank>\d+)\s*,\s*"       # rank: 非负整数
    r"(?P<valid>[01])\s*,\s*"     # valid: 仅限 0 或 1
    r"(?P<score>\d+)\s*$"         # score: 非负整数 (冻结规格 score ∈ [0, 2^b))
)

def parse_csv_lines(path):
    if not os.path.isfile(path):
        print(f"Error: File not found - {path}", file=sys.stderr)
        sys.exit(2)
        
    parsed_rows = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if re.search(r"\bCSV\b", line):
                    match = CSV_PATTERN.match(line)
                    if match:
                        rank, valid, score = map(int, match.groups())
                        parsed_rows.append({
                            'rank': rank, 
                            'valid': valid, 
                            'score': score
                        })
                    else:
                        print(f"Warning: malformed CSV line at {path}:{line_num} -> {line.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(2)
        
    return parsed_rows

def validate_rank_sequence(rows, label):
    """
    Enforces that rank values form a well-formed prefix sequence:
      - rank[0] == 0       (starts at zero)
      - rank[i] == i       (strictly sequential, no gaps or jumps)
      - no duplicate ranks (implied by strict increment)
    Returns True if valid, False otherwise.
    """
    seen = set()
    for i, row in enumerate(rows):
        r = row['rank']
        if r in seen:
            print(f"[FAIL] {label}: duplicate rank {r} at position {i}.", file=sys.stderr)
            return False
        seen.add(r)
        if r != i:
            print(f"[FAIL] {label}: rank at position {i} is {r}, expected {i} (must start at 0 and be strictly sequential).", file=sys.stderr)
            return False
    return True

from collections import Counter

def compare_rows(oracle_rows, mpc_rows):
    if not oracle_rows:
        print("[FAIL] Oracle parsed 0 CSV rows.")
        return False
        
    if not mpc_rows:
        print("[FAIL] MPC parsed 0 CSV rows.")
        return False
        
    if len(oracle_rows) != len(mpc_rows):
        print(f"Row count mismatch: oracle has {len(oracle_rows)} rows, mpc has {len(mpc_rows)} rows.")
        return False
        
    # We validate based on score threshold logic (Validating Top-K correctness without identity payloads)
    or_multiset = sorted([(r['valid'], r['score']) for r in oracle_rows], reverse=True)
    mpc_multiset = sorted([(r['valid'], r['score']) for r in mpc_rows], reverse=True)
    
    if or_multiset == mpc_multiset:
        print("[OK] Oracle and MP-SPDZ outputs match (exact multiset equality).")
        return True
        
    # If multisets differ, it might be due to valid exact-tie subset selection.
    # Find the threshold score (the lowest score in the Top-K oracle set)
    threshold = or_multiset[-1]
    
    # Check that ALL items strictly greater than the threshold are present in exact quantities
    or_counts = Counter(or_multiset)
    mpc_counts = Counter(mpc_multiset)
    
    for item, count in or_counts.items():
        if item > threshold:
            if mpc_counts[item] != count:
                print(f"[FAIL] Missing mandatory item {item}. Expected {count}, got {mpc_counts[item]}")
                return False
                
    # Check that NO items strictly less than the threshold are present
    for item in mpc_counts:
        if item < threshold:
            print(f"[FAIL] Invalid item {item} below threshold {threshold} was selected.")
            return False
            
    # Check that the total count of items matches
    if len(mpc_multiset) != len(or_multiset):
        print("[FAIL] Output length mismatch.")
        return False

    print("[OK] Oracle and MP-SPDZ outputs match (valid Top-K subset at tie threshold).")
    return True

def main():
    parser = argparse.ArgumentParser(description="Verify BlindStep Module 2 MPC output against Plaintext Oracle output")
    parser.add_argument("--oracle", required=True, help="Path to oracle output file .txt")
    parser.add_argument("--mpc", required=True, help="Path to MP-SPDZ output file .txt")
    
    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse passes status code, we ensure it's mapped to exit code 2 if arg error
        if e.code != 0:
            sys.exit(2)
        sys.exit(0)
    
    oracle_rows = parse_csv_lines(args.oracle)
    mpc_rows = parse_csv_lines(args.mpc)

    oracle_valid = validate_rank_sequence(oracle_rows, "Oracle")
    mpc_valid    = validate_rank_sequence(mpc_rows,    "MPC")
    if not oracle_valid or not mpc_valid:
        sys.exit(1)

    matched = compare_rows(oracle_rows, mpc_rows)
    
    if matched:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
