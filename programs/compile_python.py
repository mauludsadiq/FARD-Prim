#!/usr/bin/env python3
# compile_python.py -- Compile Python source to native binary via FARD Prim
#
# Usage:
#   python3 programs/compile_python.py 'def add(a,b): return a+b\nadd(10,32)' out/add
#   python3 programs/compile_python.py --file program.py out/program

import ast, json, sys, os, subprocess, tempfile

def node_to_dict(node):
    if isinstance(node, ast.AST):
        d = {"t": type(node).__name__}
        for field, value in ast.iter_fields(node):
            d[field] = node_to_dict(value)
        return d
    elif isinstance(node, list):
        return [node_to_dict(x) for x in node]
    else:
        return node


KEEP_FIELDS = {
    "Module": ["body"],
    "FunctionDef": ["name", "args", "body"],
    "arguments": ["args"],
    "arg": ["arg"],
    "Return": ["value"],
    "Expr": ["value"],
    "Call": ["func", "args"],
    "BinOp": ["left", "op", "right"],
    "UnaryOp": ["op", "operand"],
    "Compare": ["left", "ops", "comparators"],
    "BoolOp": ["op", "values"],
    "IfExp": ["test", "body", "orelse"],
    "If": ["test", "body", "orelse"],
    "While": ["test", "body"],
    "Assign": ["targets", "value"],
    "AugAssign": ["target", "op", "value"],
    "Name": ["id"],
    "Constant": ["value"],
    "Attribute": ["value", "attr"],
    "Subscript": ["value", "slice"],
    "Index": ["value"],
    "Num": ["n"],
    "Str": ["s"],
    # ops
    "Add": [], "Sub": [], "Mult": [], "Div": [], "Mod": [],
    "Eq": [], "NotEq": [], "Lt": [], "LtE": [], "Gt": [], "GtE": [],
    "And": [], "Or": [], "Not": [], "USub": [],
}

def prune_ast(node):
    if isinstance(node, dict):
        t = node.get("t", "")
        keep = KEEP_FIELDS.get(t)
        if keep is not None:
            d = {"t": t}
            for k in keep:
                if k in node:
                    d[k] = prune_ast(node[k])
            return d
        else:
            return {k: prune_ast(v) for k, v in node.items()}
    elif isinstance(node, list):
        return [prune_ast(x) for x in node]
    else:
        return node

def json_to_fard(v):
    """Convert a JSON value to a FARD literal expression."""
    if v is None:
        return "null"
    elif isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, int):
        return str(v)
    elif isinstance(v, float):
        return str(v)
    elif isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    elif isinstance(v, list):
        items = ", ".join(json_to_fard(x) for x in v)
        return f"[{items}]"
    elif isinstance(v, dict):
        pairs = ", ".join(f'"{k}": {json_to_fard(val)}' for k, val in v.items())
        return "{" + pairs + "}"
    else:
        return str(v)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} 'source' output", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            src = f.read()
        output_path = sys.argv[3]
    else:
        src = sys.argv[1].replace("\\n", "\n")
        output_path = sys.argv[2]

    # Parse Python source to AST
    tree = ast.parse(src)
    ast_dict = node_to_dict(tree)
    ast_dict = prune_ast(ast_dict)
    fard_ast = json_to_fard(ast_dict)

    # Write FARD driver
    driver = f'''import("../src/orgntr_prim/python_source_to_native") as pipeline
pipeline.compile_ast_and_emit({fard_ast}, "{output_path}")
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard',
                                     dir='tests', delete=False,
                                     prefix='py_compile_') as f:
        f.write(driver)
        driver_path = f.name

    print(f"Compiling Python -> {output_path}")
    result = subprocess.run(
        ["fardrun", "run", "--program", driver_path, "--out", "/tmp/py_compile_out"],
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
