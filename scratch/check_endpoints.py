import re

with open("backend/ai_backend.py", "r", encoding="utf-8") as f:
    content = f.read()

endpoints = re.findall(r'@app\.(get|post|put|delete|patch)\("([^"]+)"\)\s*\ndef\s+([a-zA-Z0-9_]+)\(([^)]*)\):', content)
print(f"Total endpoints: {len(endpoints)}")
for method, path, func_name, args in endpoints:
    is_protected = "get_authenticated_user" in args
    print(f"[{method.upper():6}] {path:35} -> {func_name:30} (Auth: {'YES' if is_protected else 'NO'})")
