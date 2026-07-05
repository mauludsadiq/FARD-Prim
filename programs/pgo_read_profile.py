#!/usr/bin/env python3
# pgo_read_profile.py -- Parse FARD PGO profile and print counter data
#
# Usage:
#   ./instrumented_binary 2> profile.raw
#   python3 pgo_read_profile.py profile.raw [module_info.json]
#
# Profile format: 4096 raw bytes = 512 x 64-bit little-endian counters
# Counter ID encoding: func_index * 100 + block_label
# Counter address: profile_base + counter_id * 8

import sys
import struct
import json

def parse_profile(profile_path):
    with open(profile_path, "rb") as f:
        data = f.read()
    
    if len(data) < 4096:
        print(f"Warning: profile is {len(data)} bytes, expected 4096", file=sys.stderr)
    
    counters = {}
    for i in range(min(len(data) // 8, 512)):
        val = struct.unpack_from('<q', data, i * 8)[0]
        if val != 0:
            func_idx = i // 100
            block_label = i % 100
            counters[(func_idx, block_label)] = val
    
    return counters

def print_profile(counters):
    if not counters:
        print("No non-zero counters found.")
        return
    
    print(f"{'func_idx':>8} {'block':>6} {'count':>12}")
    print("-" * 30)
    for (fi, bl), cnt in sorted(counters.items()):
        print(f"{fi:>8} {bl:>6} {cnt:>12}")
    
    print()
    total = sum(counters.values())
    print(f"Total executions: {total}")
    
    # Hot functions (by total block count)
    func_counts = {}
    for (fi, bl), cnt in counters.items():
        func_counts[fi] = func_counts.get(fi, 0) + cnt
    
    print("\nHot functions:")
    for fi, total_cnt in sorted(func_counts.items(), key=lambda x: -x[1]):
        print(f"  func[{fi}]: {total_cnt} total block executions")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} profile.raw", file=sys.stderr)
        sys.exit(1)
    
    counters = parse_profile(sys.argv[1])
    print_profile(counters)
