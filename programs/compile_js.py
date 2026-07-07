#!/usr/bin/env python3
# compile_js.py -- Compile JavaScript source to native binary via FARD Prim
#
# Requires: node + acorn  (npm install -g acorn)
# Usage:
#   python3 programs/compile_js.py 'function add(a,b){return a+b;} add(10,32);' out/add

import json, sys, os, subprocess, tempfile

def json_to_fard(v):
    if v is None: return "null"
    elif isinstance(v, bool): return "true" if v else "false"
    elif isinstance(v, int): return str(v)
    elif isinstance(v, float): return str(v)
    elif isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    elif isinstance(v, list):
        return "[" + ", ".join(json_to_fard(x) for x in v) + "]"
    elif isinstance(v, dict):
        pairs = ", ".join(f'"{k}": {json_to_fard(val)}' for k, val in v.items())
        return "{" + pairs + "}"
    else:
        return str(v)

def parse_js(src):
    """Parse JS source using acorn via node."""
    js_script = f'const acorn=require("acorn"); console.log(JSON.stringify(acorn.parse({json.dumps(src)},{{ecmaVersion:2020}})));'
    result = subprocess.run(["node", "-e", js_script], capture_output=True, text=True)
    if result.returncode != 0:
        print("acorn error:", result.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} 'js_source' output", file=sys.stderr)
        sys.exit(1)

    src = sys.argv[1].replace("\\n", "\n")
    output_path = sys.argv[2]

    ast = parse_js(src)
    fard_ast = json_to_fard(ast)

    driver = f'''import("../src/orgntr_prim/js_source_to_native") as pipeline
pipeline.compile_ast_and_emit({fard_ast}, "{output_path}")
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard',
                                     dir='tests', delete=False,
                                     prefix='js_compile_') as f:
        f.write(driver)
        driver_path = f.name

    print(f"Compiling JS -> {output_path}")
    result = subprocess.run(
        ["fardrun", "run", "--program", driver_path, "--out", "/tmp/js_compile_out"],
        capture_output=True, text=True
    )
    os.unlink(driver_path)

    if os.path.exists(output_path):
        os.chmod(output_path, 0o755)
        print(f"Written: {output_path} ({os.path.getsize(output_path)} bytes)")
    else:
        print("Compilation failed:", result.stderr[:300], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
