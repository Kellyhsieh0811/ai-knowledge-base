import ast
import pprint

with open('src/app.py', 'r') as f:
    tree = ast.parse(f.read())

funcs = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        funcs.setdefault(node.name, []).append(node.lineno)

import json
print(json.dumps({k: v for k, v in funcs.items() if len(v) > 1}, indent=2))
