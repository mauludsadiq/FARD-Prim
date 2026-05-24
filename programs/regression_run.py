#!/usr/bin/env python3
"""Run regression suite and verify native exit codes."""
import json, subprocess, os, sys

result_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/reg/result.json"

with open(result_file) as f:
    cases = json.load(f)["result"]

all_pass = True
for c in cases:
    name = c["name"]
    expected = c["expected"]
    if not c["compiled"]:
        print(f"FAIL {name}: compile error — {c.get('err','?')}")
        all_pass = False
        continue
    out = c["out"]
    os.chmod(out, 0o755)
    r = subprocess.run([out], capture_output=True, timeout=5)
    got = r.returncode
    ok = got == expected
    if not ok:
        all_pass = False
    print(f"{'PASS' if ok else 'FAIL'} {name}: got={got} expected={expected}")

print()
print("ALL PASS" if all_pass else "FAILURES DETECTED")
sys.exit(0 if all_pass else 1)
