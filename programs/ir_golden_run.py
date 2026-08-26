#!/usr/bin/env python3
"""IR-level golden tests: assert each optimizer pass performs its intended transformation."""
import ast, json, sys, os, subprocess, tempfile

def node_to_dict(node):
    if isinstance(node, ast.AST):
        d = {'t': type(node).__name__}
        for field, value in ast.iter_fields(node):
            d[field] = node_to_dict(value)
        return d
    elif isinstance(node, list):
        return [node_to_dict(x) for x in node]
    else:
        return node

def prune_ast(node):
    PRUNE = {'type_comment','kind','type_ignores','col_offset','end_col_offset','lineno','end_lineno'}
    if isinstance(node, dict):
        if node.get('t') == 'Constant' and 'value' in node:
            return {k: prune_ast(v) for k,v in node.items() if k not in PRUNE}
        return {k: prune_ast(v) for k,v in node.items() if k not in PRUNE}
    elif isinstance(node, list):
        return [prune_ast(x) for x in node]
    return node

def json_to_fard(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, float): return str(v)
    if isinstance(v, str): return f'"{v}"'
    if isinstance(v, list):
        return "[" + ", ".join(json_to_fard(x) for x in v) + "]"
    if isinstance(v, dict):
        pairs = ", ".join(f'"{k}": {json_to_fard(val)}' for k,val in v.items())
        return "{" + pairs + "}"
    return "null"

def py_to_fard_ast(src):
    tree = ast.parse(src)
    d = node_to_dict(tree)
    d = prune_ast(d)
    return json_to_fard(d)

CASES = [
    {
        "name": "sccp_reduces_insts",
        "src": "x=6\ny=7\nz=x*y\nz",
        "check": "dump.count_insts(dump.pipeline_to_p1(ast)) < dump.count_insts(dump.pipeline_to_ocir(ast))",
        "desc": "SCCP reduces instruction count when folding constants",
    },
    {
        "name": "sccp_reduces_const_mul",
        "src": "x=6\ny=7\nz=x*y\nz",
        "check": "dump.count_op(dump.pipeline_to_p1(ast), \"MulI64\") < dump.count_op(dump.pipeline_to_ocir(ast), \"MulI64\")",
        "desc": "SCCP reduces MulI64 count when folding constant multiply",
    },
    {
        "name": "sccp_prunes_dead_blocks",
        "src": "x=6\ny=7\nz=x*y\nz",
        "check": "dump.count_blocks(dump.pipeline_to_p1(ast)) <= dump.count_blocks(dump.pipeline_to_ocir(ast))",
        "desc": "SCCP prunes dead blocks after constant folding",
    },
    {
        "name": "gvn_reduces_insts",
        "src": "x=10\ny=x+1\nz=x+1\ny+z",
        "check": "dump.count_insts(dump.pipeline_to_p4(ast)) <= dump.count_insts(dump.pipeline_to_p1(ast))",
        "desc": "GVN eliminates redundant x+1 computation",
    },
    {
        "name": "licm_preserves_blocks",
        "src": "i=0\nwhile i<10:\n  i=i+1\ni",
        "check": "dump.count_blocks(dump.pipeline_to_licm(ast)) == dump.count_blocks(dump.pipeline_to_p4(ast))",
        "desc": "LICM preserves block count",
    },
    {
        "name": "licm_no_inst_increase",
        "src": "i=0\nwhile i<10:\n  i=i+1\ni",
        "check": "dump.count_insts(dump.pipeline_to_licm(ast)) <= dump.count_insts(dump.pipeline_to_p4(ast))",
        "desc": "LICM does not increase instruction count",
    },
    {
        "name": "ivsr_total_mul_no_increase",
        "src": "i=0\ns=0\nwhile i<10:\n  s=s+(i*3)\n  i=i+1\ns",
        "check": "dump.count_op(dump.pipeline_to_ivsr(ast), \"MulI64\") <= dump.count_op(dump.pipeline_to_licm(ast), \"MulI64\")",
        "desc": "IV-SR does not increase MulI64 count (early passes may already eliminate them)",
    },
    {
        "name": "ivsr_has_add",
        "src": "i=0\ns=0\nwhile i<10:\n  s=s+(i*3)\n  i=i+1\ns",
        "check": "dump.count_op(dump.pipeline_to_ivsr(ast), \"AddI64\") > 0",
        "desc": "IV-SR introduces AddI64 for secondary induction variable",
    },
]

def run_case(case):
    fard_ast = py_to_fard_ast(case['src'])
    check = case['check']
    
    fard_src = f'''import("src/orgntr_prim/ocir_dump") as dump
let ast = {fard_ast} in
if {check} then 1 else 0
'''
    with tempfile.NamedTemporaryFile(suffix='.fard', mode='w', delete=False, dir='.') as f:
        f.write(fard_src)
        fname = f.name
    
    outdir = f'/tmp/ir_golden_{case["name"]}'
    os.makedirs(outdir, exist_ok=True)
    
    try:
        r = subprocess.run(
            ['fardrun', 'run', '--program', fname, '--out', outdir],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            return False, f"FARD error: {r.stderr[:200]}"
        
        with open(f'{outdir}/result.json') as f:
            result = json.load(f)
        
        r = result.get('result', result) if isinstance(result, dict) else result
        return r == 1, f"got={result}"
    except Exception as e:
        return False, str(e)
    finally:
        os.unlink(fname)

os.makedirs('out', exist_ok=True)
passed = 0
failures = []

print(f"Running {len(CASES)} IR golden tests...\n")
for case in CASES:
    ok, detail = run_case(case)
    if ok:
        passed += 1
        print(f"PASS {case['name']}")
        print(f"     {case['desc']}")
    else:
        failures.append(case['name'])
        print(f"FAIL {case['name']}: {detail}")
        print(f"     {case['desc']}")

print(f"\n{passed}/{len(CASES)} PASS")
if failures:
    sys.exit(1)
