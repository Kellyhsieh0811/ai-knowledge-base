import ast

with open('src/app.py', 'r') as f:
    tree = ast.parse(f.read())

funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
from collections import Counter
dups = [item for item, count in Counter(funcs).items() if count > 1]
unique = [item for item, count in Counter(funcs).items() if count == 1]
print("Duplicates:", dups)
