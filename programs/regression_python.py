#!/usr/bin/env python3
"""Python frontend regression suite for FARD Prim.
Tests: basic ops, if/else, while, closures, lists, print, jump threading,
       loop fusion, precise GC, typed IR, return-in-if, branch assignments.
Run: python3 programs/regression_python.py
"""
import ast, json, subprocess, os, sys, time, tempfile

def compile_py(src, outpath):
    """Compile Python source to native binary. Returns (ok, err)."""
    if os.path.exists(outpath):
        os.unlink(outpath)
    r = subprocess.run(
        ['python3', 'programs/compile_python.py', src, outpath],
        capture_output=True, text=True
    )
    if os.path.exists(outpath):
        os.chmod(outpath, 0o755)
        return True, None
    return False, r.stderr[:200]

def run_bin(path, timeout=5):
    """Run binary, return exit code."""
    r = subprocess.run([path], capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode()

cases = [
    # ── Basic arithmetic ──────────────────────────────────────────
    ("arith_add",      "1 + 2 + 3",                                        6),
    ("arith_mul",      "6 * 7",                                            42),
    ("arith_sub",      "50 - 8",                                           42),
    ("arith_mod",      "100 % 58",                                         42),
    ("arith_neg",      "0 - 42",                                          214),  # -42 % 256

    # ── Functions ────────────────────────────────────────────────
    ("fn_basic",       "def f(x): return x + 1\nf(41)",                   42),
    ("fn_multi_arg",   "def f(a,b,c): return a+b+c\nf(10,20,12)",        42),
    ("fn_recursive",   "def f(n):\n  if n <= 1: return 1\n  return n * f(n-1)\nf(5)", 120),
    ("fn_fib",         "def f(n):\n  if n <= 1: return n\n  return f(n-1)+f(n-2)\nf(10)", 55),

    # ── If/else + branch assignments ─────────────────────────────
    ("if_true",        "x = 0\nif 1:\n  x = 42\nx",                      42),
    ("if_false",       "x = 99\nif 0:\n  x = 1\nelse:\n  x = 42\nx",    42),
    ("if_both_branches","x=0\ny=0\nif 1:\n  x=10\n  y=32\nelse:\n  x=0\n  y=0\nx+y", 42),
    ("if_in_fn",       "def f(n):\n  x=0\n  if n>5:\n    x=1\n  else:\n    x=2\n  return x\nf(10)+f(1)", 3),
    ("return_in_if",   "def f(n):\n  if n>5:\n    return 1\n  return 0\nf(10)+f(3)", 1),
    ("nested_if",      "def f(n):\n  if n>10:\n    if n>20:\n      return 3\n    return 2\n  return 1\nf(25)+f(15)+f(5)", 6),

    # ── While loops ──────────────────────────────────────────────
    ("while_basic",    "i=0\nwhile i<10:\n  i=i+1\ni",                   10),
    ("while_sum",      "i=0\ntotal=0\nwhile i<10:\n  total=total+i\n  i=i+1\ntotal", 45),
    ("while_nested",   "i=0\ntotal=0\nwhile i<5:\n  j=0\n  while j<i:\n    total=total+1\n    j=j+1\n  i=i+1\ntotal", 10),

    # ── Loop fusion (two adjacent loops, same bound) ──────────────
    ("loop_fusion",    "i=0\nwhile i<5:\n  i=i+1\nj=0\nwhile j<5:\n  j=j+1\ni+j", 10),
    ("loop_fusion2",   "xs=[0,0,0]\ni=0\nwhile i<3:\n  xs[i]=i+1\n  i=i+1\ntotal=0\nj=0\nwhile j<3:\n  total=total+xs[j]\n  j=j+1\ntotal", 6),

    # ── Jump threading ────────────────────────────────────────────
    ("jt_const_true",  "x=0\nif 1:\n  x=42\nelse:\n  x=0\nx",           42),
    ("jt_chain",       "def f(x):\n  flag=1\n  y=0\n  if flag:\n    y=x+1\n  else:\n    y=x-1\n  return y\nf(41)", 42),

    # ── Lists ────────────────────────────────────────────────────
    ("list_idx",       "xs=[10,20,30]\nxs[0]+xs[2]",                     40),
    ("list_append",    "xs=[1,2,3]\nxs.append(4)\nlen(xs)",               4),
    ("list_pop",       "xs=[1,2,3,4]\nxs.pop()\nlen(xs)",                 3),
    ("list_len",       "xs=[1,2,3,4,5]\nlen(xs)",                         5),
    ("list_assign",    "xs=[0,0,0]\nxs[1]=42\nxs[1]",                    42),

    # ── Closures ─────────────────────────────────────────────────
    ("closure_basic",  "def adder(x):\n  def inner(y): return x+y\n  return inner\nadder(10)(32)", 42),
    ("closure_capture","def make(n):\n  def f(): return n*2\n  return f\nmake(21)()", 42),

    # ── Precise GC under pressure ─────────────────────────────────
    ("gc_pressure",    "i=0\ntotal=0\nwhile i<1000:\n  xs=[i,i+1,i+2]\n  total=total+xs[0]\n  i=i+1\ntotal%256", 44),

    # ── print_int (side-effect, check via exit code) ───────────────
    ("print_int",      "print_int(42)\n0",                                0),
    ("str_len",       "len(\"hello\")",                               5),
    ("str_concat",    "a=\"hi\"\\nb=\"!\"\\nc=a+b\\nlen(c)", 3),
    ("str_eq_true",   "a=\"x\"\\nb=\"x\"\\na==b",              1),
    ("str_eq_false",  "a=\"x\"\\nb=\"y\"\\na==b",              0),
    ("str_conv",      "s=str(42)\nlen(s)",                                2),
    ("str_len",        "len(\"hello\")",                                    5),
]

passed = 0
failed = 0
errors = []

print(f"Running {len(cases)} Python regression cases...\n")

for name, src, expected in cases:
    outpath = f"out/pytest_{name}"
    try:
        ok, err = compile_py(src, outpath)
        if not ok:
            print(f"FAIL {name}: compile error: {err}")
            failed += 1
            errors.append(name)
            continue
        got, stdout = run_bin(outpath)
        # Normalize expected to 0-255 range (exit code)
        exp_code = expected % 256
        if got == exp_code:
            print(f"PASS {name}: exit={got}")
            passed += 1
        else:
            print(f"FAIL {name}: got={got} expected={exp_code} (raw={expected})")
            failed += 1
            errors.append(name)
    except Exception as e:
        print(f"FAIL {name}: exception: {e}")
        failed += 1
        errors.append(name)
    finally:
        if os.path.exists(outpath):
            os.unlink(outpath)

print(f"\n{passed}/{passed+failed} PASS", end="")
if errors:
    print(f"  FAILED: {', '.join(errors)}")
else:
    print("  ALL PASS")

sys.exit(0 if failed == 0 else 1)
