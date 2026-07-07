#!/usr/bin/env python3
# py_to_json.py -- Convert Python source to AST JSON for python_to_uvir
#
# Usage:
#   python3 programs/py_to_json.py 'def add(a,b): return a+b\nadd(10,32)'
#   python3 programs/py_to_json.py --file program.py
#
# Output: JSON AST compatible with python_to_uvir.lower_module()

import ast
import json
import sys

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

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} 'source' | --file path.py", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            src = f.read()
    else:
        src = sys.argv[1].replace("\\n", "\n")

    tree = ast.parse(src)
    print(json.dumps(node_to_dict(tree), indent=2))

if __name__ == "__main__":
    main()
