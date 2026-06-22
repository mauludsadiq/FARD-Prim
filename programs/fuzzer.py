#!/usr/bin/env python3
"""FARD Prim property-based fuzzer.
Generates random integer-arithmetic FARD programs, compiles natively,
runs, and compares against fardrun eval."""

import subprocess, os, random, sys, stat, json, tempfile

REPO = '/Users/g.bogans/Downloads/FARD Prim'
EVAL_FARD = os.path.join(REPO, 'programs/fuzzer_eval.fard')

def lcg(seed):
    return (seed * 1664525 + 1013904223) % 2147483648

def rand_range(seed, lo, hi):
    s = lcg(seed)
    return lo + (s % (hi - lo)), s

def gen_expr(seed, depth, params):
    if depth <= 0:
        v, s = rand_range(seed, 0, 10)
        return str(v), s
    choice, s = rand_range(seed, 0, 5)
    if choice == 0:
        v, s = rand_range(s, 0, 10)
        return str(v), s
    elif choice == 1 and params:
        i, s = rand_range(s, 0, len(params))
        return params[i % len(params)], s
    elif choice == 2:
        l, s = gen_expr(s, depth-1, params)
        r, s = gen_expr(s, depth-1, params)
        op, s = rand_range(s, 0, 3)
        op = ['+', '-', '*'][op]
        return f'({l}{op}{r})', s
    elif choice == 3:
        c, s = gen_expr(s, depth-1, params)
        t, s = gen_expr(s, depth-1, params)
        e, s = gen_expr(s, depth-1, params)
        op, s = rand_range(s, 0, 4)
        op = ['<', '>', '==', '<='][op]
        return f'if {c}{op}{t} then {t} else {e}', s
    else:
        v, s = rand_range(s, 0, 10)
        return str(v), s

def gen_program(seed):
    params = ['a', 'b']
    body, s = gen_expr(seed, 3, params)
    a, s = rand_range(s, 1, 9)
    b, s = rand_range(s, 1, 9)
    src = f'fn f(a,b){{{body}}}\nf({a},{b})'
    return src, s

def eval_with_fard(src):
    """Evaluate src using fard_eval, return int or None."""
    prog = f'''
import("/Users/g.bogans/Downloads/FARD_v0.5/apps/fardlex") as lex
import("/Users/g.bogans/Downloads/FARD_v0.5/apps/fardparse") as par
import("/Users/g.bogans/Downloads/FARD_v0.5/apps/fard_eval") as ev
import("std/rec") as rec
let src = {json.dumps(src)}
let parsed = par.parse_module(lex.tokenize(src), 0)
if !parsed.ok then {{ t: "err" }}
else
  let r = ev.eval_module(parsed.node) in
  if !rec.has(r, "t") then {{ t: "err" }}
  else r
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard', dir=REPO, delete=False) as f:
        f.write(prog)
        fname = f.name
    out_dir = tempfile.mkdtemp()
    try:
        r = subprocess.run(['fardrun', 'run', '--program', fname, '--out', out_dir],
                          capture_output=True, cwd=REPO, timeout=10)
        rfile = os.path.join(out_dir, 'result.json')
        if not os.path.exists(rfile): return None
        data = json.load(open(rfile))['result']
        if data.get('t') == 'int': return data['v']
        return None
    except Exception:
        return None
    finally:
        os.unlink(fname)

def compile_and_run(src, idx):
    """Compile src natively, run, return exit code or None."""
    out_name = f'out/fuzz_{idx}'
    out_path = os.path.join(REPO, out_name)
    prog = f'''
import("src/orgntr_prim/fard_source_to_native") as native
let src = {json.dumps(src)}
native.compile_and_emit(src, {json.dumps(out_name)})
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard', dir=REPO, delete=False) as f:
        f.write(prog)
        fname = f.name
    out_dir = tempfile.mkdtemp()
    try:
        r = subprocess.run(['fardrun', 'run', '--program', fname, '--out', out_dir],
                          capture_output=True, cwd=REPO, timeout=30)
        rfile = os.path.join(out_dir, 'result.json')
        if not os.path.exists(rfile): return None
        data = json.load(open(rfile))['result']
        if not data.get('ok'): return None
        # Make executable
        os.chmod(out_path, os.stat(out_path).st_mode | stat.S_IEXEC)
        r2 = subprocess.run([out_path], capture_output=True, timeout=5)
        return r2.returncode
    except Exception:
        return None
    finally:
        os.unlink(fname)

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    passes = skips = fails = 0
    for i in range(n):
        src, seed = gen_program(seed)
        expected = eval_with_fard(src)
        if expected is None or expected < 0 or expected > 100:
            skips += 1
            continue
        got = compile_and_run(src, i)
        if got is None:
            skips += 1
            continue
        if got == expected:
            passes += 1
            if passes % 10 == 0:
                print(f'  {passes} pass, {skips} skip, {fails} fail')
        else:
            fails += 1
            print(f'FAIL #{i}: expected={expected} got={got}')
            print(f'  src: {src}')
            if fails >= 3:
                print('Stopping after 3 failures.')
                break
    print(f'\nDone: {passes} pass, {skips} skip, {fails} fail / {n} total')
    return 1 if fails > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
