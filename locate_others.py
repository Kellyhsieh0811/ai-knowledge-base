import ast

with open('src/app.py', 'r') as f:
    tree = ast.parse(f.read())

funcs = {node.name: node.lineno for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
print({k: funcs[k] for k in ['ai_rewrite', 'ai_translate', 'ai_extract_topics'] if k in funcs})
