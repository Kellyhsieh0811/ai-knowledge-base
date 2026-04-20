with open('src/app.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    lineno = i + 1
    if 529 <= lineno <= 604:
        continue
    if 651 <= lineno <= 755:
        continue
    new_lines.append(line)

with open('src/app.py', 'w') as f:
    f.writelines(new_lines)
