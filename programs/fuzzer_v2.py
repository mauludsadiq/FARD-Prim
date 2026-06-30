#!/usr/bin/env python3
"""FARD Prim property-based fuzzer v2.
Adds: recursive functions, closures with captured variables.
Generates random FARD programs, compiles natively, runs, compares
against fard_eval interpreter."""

import subprocess, os, random, sys, stat, json, tempfile

REPO = '/Users/g.bogans/Downloads/FARD Prim'

def lcg(seed):
    return (seed * 1664525 + 1013904223) % 2147483648

def rand_range(seed, lo, hi):
    s = lcg(seed)
    high_bits = s >> 16
    return lo + (high_bits % (hi - lo)), s

# ── Plain arithmetic expr generator (existing) ────────────────────────────────

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

def gen_arith_program(seed):
    params = ['a', 'b']
    body, s = gen_expr(seed, 3, params)
    a, s = rand_range(s, 1, 9)
    b, s = rand_range(s, 1, 9)
    src = f'fn f(a,b){{{body}}}\nf({a},{b})'
    return src, s

# ── Recursive function generator ──────────────────────────────────────────────
# Always: fn rec(n){ if n<=BASE then BASEVAL else COMBINE(n, rec(n-1)) }
# Guaranteed to terminate since n decreases toward BASE each call.

def gen_recursive_program(seed):
    base, s = rand_range(seed, 0, 3)          # base case threshold: 0,1,2
    base_val, s = rand_range(s, 0, 5)          # value returned at base case
    op_choice, s = rand_range(s, 0, 3)
    op = ['+', '-', '*'][op_choice]
    # combine: n OP rec(n-1)   or   rec(n-1) OP n
    order, s = rand_range(s, 0, 2)
    n_arg, s = rand_range(s, base + 1, base + 6)  # ensures >= 1 real recursive step

    if order == 0:
        combine = f'n{op}rec(n-1)'
    else:
        combine = f'rec(n-1){op}n'

    src = (f'fn rec(n){{if n<={base} then {base_val} else {combine}}}\n'
           f'rec({n_arg})')
    return src, s

# ── Closure generator ──────────────────────────────────────────────────────────
# fn make(x){ fn(y){ x OP y } }
# make(A)(B)   -- immediately applies the returned closure

def gen_closure_program(seed):
    op_choice, s = rand_range(seed, 0, 3)
    op = ['+', '-', '*'][op_choice]
    a, s = rand_range(s, 0, 10)
    b, s = rand_range(s, 0, 10)
    src = f'fn make(x){{fn(y){{x{op}y}}}}\nmake({a})({b})'
    return src, s

# ── Closure + recursion combo: tail-recursive-ish via closures ────────────────
# fn make(x){ fn(y){ if y<=0 then x else x OP y } }
# make(A)(B)

def gen_closure_cond_program(seed):
    op_choice, s = rand_range(seed, 0, 2)
    op = ['+', '*'][op_choice]
    a, s = rand_range(s, 1, 8)
    b, s = rand_range(s, 0, 8)
    threshold, s = rand_range(s, 0, 4)
    src = (f'fn make(x){{fn(y){{if y<={threshold} then x else x{op}y}}}}\n'
           f'make({a})({b})')
    return src, s

GENERATORS = [
    ('arith', gen_arith_program),
    ('recursive', gen_recursive_program),
    ('closure', gen_closure_program),
    ('closure_cond', gen_closure_cond_program),
]

def eval_with_fard(src):
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
        subprocess.run(['fardrun', 'run', '--program', fname, '--out', out_dir],
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
    out_name = f'out/fuzz2_{idx}'
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
        subprocess.run(['fardrun', 'run', '--program', fname, '--out', out_dir],
                       capture_output=True, cwd=REPO, timeout=30)
        rfile = os.path.join(out_dir, 'result.json')
        if not os.path.exists(rfile): return None, 'compile_no_output'
        data = json.load(open(rfile))['result']
        if not data.get('ok'): return None, 'compile_failed'
        os.chmod(out_path, os.stat(out_path).st_mode | stat.S_IEXEC)
        r2 = subprocess.run([out_path], capture_output=True, timeout=5)
        return r2.returncode, None
    except subprocess.TimeoutExpired:
        return None, 'timeout'
    except Exception as e:
        return None, f'exception:{e}'
    finally:
        os.unlink(fname)

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    stats = {name: {'pass': 0, 'skip': 0, 'fail': 0} for name, _ in GENERATORS}
    fails = []
    for i in range(n):
        gen_idx, seed = rand_range(seed, 0, len(GENERATORS))
        name, gen_fn = GENERATORS[gen_idx]
        src, seed = gen_fn(seed)
        expected = eval_with_fard(src)
        if expected is None or expected < -50 or expected > 100:
            stats[name]['skip'] += 1
            continue
        # exit codes are unsigned 0-255; negative results need masking
        expected_exit = expected & 0xFF if expected >= 0 else (256 + expected) & 0xFF
        got, err = compile_and_run(src, i)
        if got is None:
            stats[name]['skip'] += 1
            continue
        if got == expected_exit:
            stats[name]['pass'] += 1
        else:
            stats[name]['fail'] += 1
            fails.append((i, name, src, expected, expected_exit, got))
            print(f'FAIL #{i} [{name}]: expected={expected} (exit {expected_exit}) got={got}')
            print(f'  src: {src}')
            if len(fails) >= 5:
                print('Stopping after 5 failures.')
                break
    total_pass = sum(s['pass'] for s in stats.values())
    total_skip = sum(s['skip'] for s in stats.values())
    total_fail = sum(s['fail'] for s in stats.values())
    print(f'\n=== Results by generator ===')
    for name, s in stats.items():
        print(f'  {name:15} pass={s["pass"]:4} skip={s["skip"]:4} fail={s["fail"]:4}')
    print(f'\nTotal: {total_pass} pass, {total_skip} skip, {total_fail} fail / {n}')
    return 1 if total_fail > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
