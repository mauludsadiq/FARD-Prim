#!/usr/bin/env python3
"""
Pass instrumentation benchmark.
Compiles each benchmark program through each pipeline stage,
measures instruction/block counts before and after each pass,
and writes a JSON report to benchmarks/YYYYMMDD_HHMMSS.json
"""
import ast, json, sys, os, subprocess, tempfile, datetime

def node_to_dict(node):
    if isinstance(node, ast.AST):
        d = {'t': type(node).__name__}
        for field, value in ast.iter_fields(node):
            d[field] = node_to_dict(value)
        return d
    elif isinstance(node, list): return [node_to_dict(x) for x in node]
    else: return node

def prune_ast(node):
    PRUNE = {'type_comment','kind','type_ignores','col_offset','end_col_offset','lineno','end_lineno'}
    if isinstance(node, dict): return {k: prune_ast(v) for k,v in node.items() if k not in PRUNE}
    elif isinstance(node, list): return [prune_ast(x) for x in node]
    return node

def json_to_fard(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, float): return str(v)
    if isinstance(v, str): return f'"{v}"'
    if isinstance(v, list): return "[" + ", ".join(json_to_fard(x) for x in v) + "]"
    if isinstance(v, dict):
        pairs = ", ".join(f'"{k}": {json_to_fard(val)}' for k,val in v.items())
        return "{" + pairs + "}"
    return "null"

def py_to_fard_ast(src):
    return json_to_fard(prune_ast(node_to_dict(ast.parse(src))))

BENCHMARKS = [
    ("arith_const",   "x=6\ny=7\nz=x*y\nz",
     "constant multiply — SCCP target"),
    ("arith_redundant","x=10\ny=x+1\nz=x+1\ny+z",
     "redundant expression — GVN target"),
    ("while_simple",  "i=0\nwhile i<10:\n  i=i+1\ni",
     "simple loop — LICM target"),
    ("while_ivsr",    "i=0\ns=0\nwhile i<10:\n  s=s+(i*3)\n  i=i+1\ns",
     "induction variable multiply — IV-SR target"),
    ("while_nested",  "i=0\ntotal=0\nwhile i<5:\n  j=0\n  while j<i:\n    total=total+1\n    j=j+1\n  i=i+1\ntotal",
     "nested loops — LICM+fusion target"),
    ("fn_recursive",  "def fact(n):\n  if n==0: return 1\n  return n*fact(n-1)\nfact(5)",
     "recursive function — inline+SCCP target"),
    ("fn_fib",        "def fib(n):\n  if n<=1: return n\n  return fib(n-1)+fib(n-2)\nfib(10)",
     "doubly recursive — inline target"),
    ("closure",       "def adder(x):\n  def inner(y): return x+y\n  return inner\nadder(10)(32)",
     "closure capture — general"),
    ("list_ops",      "xs=[1,2,3,4,5]\nxs[0]+xs[4]",
     "list indexing — load/store target"),
    ("while_sum",     "i=0\ns=0\nwhile i<100:\n  s=s+i\n  i=i+1\ns%256",
     "accumulator loop — IV-SR+LICM target"),
]

PASSES = ["ocir", "sccp", "inline", "gvn", "licm", "ivsr"]

def collect_metrics(src):
    fard_ast = py_to_fard_ast(src)
    fard_src = f'''import("src/orgntr_prim/ocir_dump") as dump
let ast = {fard_ast} in
dump.pass_metrics(ast)
'''
    with tempfile.NamedTemporaryFile(suffix='.fard', mode='w', delete=False, dir='.') as f:
        f.write(fard_src)
        fname = f.name

    outdir = '/tmp/bench_metrics'
    os.makedirs(outdir, exist_ok=True)
    try:
        r = subprocess.run(
            ['fardrun', 'run', '--program', fname, '--out', outdir],
            capture_output=True, text=True, timeout=180
        )
        if r.returncode != 0:
            return None, r.stderr[:200]
        result = json.load(open(f'{outdir}/result.json'))
        return result.get('result', result), None
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(fname)

def reduction(before, after, key):
    b, a = before.get(key, 0), after.get(key, 0)
    if b == 0: return 0
    return round((b - a) / b * 100, 1)

os.makedirs('benchmarks', exist_ok=True)
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

# Get git commit
try:
    commit = subprocess.check_output(['git','rev-parse','--short','HEAD']).decode().strip()
except: commit = 'unknown'

report = {
    'timestamp': timestamp,
    'commit': commit,
    'benchmarks': []
}

print(f"Commit: {commit}")
print(f"{'Benchmark':<20} {'Desc':<35} {'OCIR':>6} {'SCCP':>6} {'GVN':>6} {'LICM':>6} {'IVSR':>6} {'Total%':>7}")
print('-' * 90)

for name, src, desc in BENCHMARKS:
    print(f"{name:<20} {desc:<35}", end='', flush=True)
    metrics, err = collect_metrics(src)
    if err:
        print(f"  ERROR: {err[:50]}")
        continue

    row = {'name': name, 'desc': desc, 'passes': metrics}
    report['benchmarks'].append(row)

    ocir  = metrics.get('ocir',   {}).get('insts', 0)
    sccp  = metrics.get('sccp',   {}).get('insts', 0)
    gvn   = metrics.get('gvn',    {}).get('insts', 0)
    licm  = metrics.get('licm',   {}).get('insts', 0)
    ivsr  = metrics.get('ivsr',   {}).get('insts', 0)
    total = round((ocir - ivsr) / ocir * 100, 1) if ocir > 0 else 0

    print(f" {ocir:>6} {sccp:>6} {gvn:>6} {licm:>6} {ivsr:>6} {total:>6}%")

print('-' * 90)

# Save report
report_path = f'benchmarks/{timestamp}_{commit}.json'
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)
print(f"\nReport saved: {report_path}")

# Save latest symlink
import shutil
shutil.copy(report_path, 'benchmarks/latest.json')
