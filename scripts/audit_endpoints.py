import re

with open("backend/ai_backend.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find all route definitions
matches = re.findall(r"@app\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", content)
print(f"Total routes found: {len(matches)}")
for method, path in matches:
    print(f"{method.upper():6} {path}")
