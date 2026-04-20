import re
with open('src/notion_service.py', 'r') as f:
    content = f.read()

# Just replace conflict markers by keeping the latter part which in this rebase 
# usually contains the intended fix (like "0917904")
new_content = re.sub(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> 0917904[^\n]*\n', lambda m: m.group(2), content, flags=re.DOTALL)

with open('src/notion_fixed.py', 'w') as f:
    f.write(new_content)
