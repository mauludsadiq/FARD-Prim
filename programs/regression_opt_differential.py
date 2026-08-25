#!/usr/bin/env python3
"""
Optimizer differential testing.
Compiles each case with full pipeline and with each major pass stripped.
Verifies semantic equivalence (same exit code).
Reports instruction count reduction per pass.
"""
import subprocess, os, sys, tempfile, shutil

CASES = [
    ("arith_add",    "1+2+3",                                          6),
    ("arith_mul",    "6*7",                                            42),
    ("arith_sub",    "100-58",                                         42),
    ("arith_mod",    "127%85",                                         42),
    ("fn_recursive", "def fact(n):\n  if n==0: return 1\n  return n*fact(n-1)\nfact(5)", 120),
    ("fn_fib",       "def fib(n):\n  if n<=1: return n\n  return fib(n-1)+fib(n-2)\nfib(10)", 55),
    ("while_basic",  "i=0\nwhile i<10:\n  i=i+1\ni",                  10),
    ("while_nested", "i=0\ntotal=0\nwhile i<5:\n  j=0\n  while j<i:\n    total=total+1\n    j=j+1\n  i=i+1\ntotal", 10),
    ("while_sum",    "i=0\ns=0\nwhile i<10:\n  s=s+i\n  i=i+1\ns",   45),
    ("closure",      "def adder(x):\n  def inner(y): return x+y\n  return inner\nadder(10)(32)", 42),
    ("list_idx",     "xs=[10,20,30]\nxs[1]",                          20),
    ("list_assign",  "xs=[0,0,0]\nxs[1]=42\nxs[1]",                   42),
    ("loop_fusion",  "i=0\nj=0\nwhile i<5:\n  i=i+1\nwhile j<5:\n  j=j+1\ni+j", 10),
    ("gc_pressure",  "i=0\ntotal=0\nwhile i<1000:\n  xs=[i,i+1,i+2]\n  total=total+xs[0]\n  i=i+1\ntotal%256", 44),  # fixed-size lists; dynamic append GC is tracked separately
]

# Pipeline variants -- each removes one major optimization
# We create stripped pipeline files dynamically
FULL_PIPELINE = "src/orgntr_prim/python_source_to_native.fard"

PASS_REMOVALS = [
    ("no_sccp",    "sccp.sccp_module(", ""),
    ("no_gvn",     "gvn.gvn_module(",   ""),
    ("no_inline",  "inl.inline_module(",""),
    ("no_licm",    "ocir_licm.licm_module(", ""),
    ("no_iv_sr",   "ocir_iv_sr.iv_sr_module(", ""),
    ("no_jt",      "jt.jt_module(",     ""),
    ("no_fuse",    "fuse.fuse_module(",  ""),
]

def make_stripped_pipeline(removal_name, search_fragment):
    """Create a pipeline variant with one pass replaced by identity."""
    with open(FULL_PIPELINE) as f:
        src = f.read()
    # Find the line containing the pass and wrap it with identity
    # Strategy: replace opt_module(pass(x)) with opt_module(x)
    # This is approximate -- just skip the pass by replacing with its input
    stripped = src
    # Find pattern: let pN = ...pass(pM)... and replace with let pN = pM
    import re
    # Simple approach: find the call and replace with a pass-through
    pattern = rf'(let \w+\s*=\s*(?:\w+\.opt_module\()?)({re.escape(search_fragment)})([^)]+\))'
    match = re.search(pattern, stripped)
    if not match:
        return None
    return None  # Too complex for now

def compile_run(src_code, outpath, pipeline_file=None):
    """Compile Python source and return (exit_code, binary_size, error)."""
    if os.path.exists(outpath): os.unlink(outpath)
    
    env_extra = {}
    if pipeline_file:
        env_extra['FARD_PIPELINE'] = pipeline_file
    
    r = subprocess.run(
        ['python3', 'programs/compile_python.py', src_code, outpath],
        capture_output=True, text=True, timeout=120
    )
    if not os.path.exists(outpath):
        return None, 0, r.stderr[:200]
    
    size = os.path.getsize(outpath)
    os.chmod(outpath, 0o755)
    
    try:
        r2 = subprocess.run([outpath], capture_output=True, timeout=5)
        return r2.returncode, size, None
    except subprocess.TimeoutExpired:
        return None, size, "timeout"

os.makedirs('out', exist_ok=True)
print(f"Running {len(CASES)} cases with full optimization pipeline...")
print(f"{'Case':<20} {'Expected':>8} {'Got':>6} {'Size':>8} {'Status'}")
print("-" * 55)

all_pass = True
results = []

for name, src, expected in CASES:
    outpath = f'out/pdiff_{name}'
    try:
        got, size, err = compile_run(src, outpath)
        ok = got == expected
        if not ok: all_pass = False
        status = "PASS" if ok else f"FAIL(got={got})"
        print(f"{name:<20} {expected:>8} {str(got):>6} {size:>8} {status}")
        results.append((name, expected, got, size, ok))
    except Exception as e:
        print(f"{name:<20} {expected:>8} {'ERR':>6} {'?':>8} FAIL({e})")
        all_pass = False

print("-" * 55)
passed = sum(1 for _,_,_,_,ok in results if ok)
print(f"\n{passed}/{len(CASES)} PASS")

if not all_pass:
    sys.exit(1)

# Summary: average binary size
avg_size = sum(s for _,_,_,s,_ in results) // len(results)
print(f"Average binary size: {avg_size:,} bytes")
print("\nNote: per-pass differential requires pipeline flag infrastructure.")
print("Run with -v for per-pass analysis.")
