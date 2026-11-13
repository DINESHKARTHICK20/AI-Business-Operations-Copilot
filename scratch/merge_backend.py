import os

BACKEND_FILE = r"d:\My Projects\AI Business Operations Copilot\backend\ai_backend.py"
NEW_ENDPOINTS_FILE = r"d:\My Projects\AI Business Operations Copilot\scratch\new_endpoints.py.txt"

with open(BACKEND_FILE, "r", encoding="utf-8") as f:
    content = f.read()

marker = "# ============================================================\n# 1. CUSTOMERS APIS\n# ============================================================"
if marker not in content:
    raise RuntimeError("Customers marker not found in ai_backend.py")

prefix = content.split(marker)[0]

spa_marker = "# ============================================================\n# SPA CLIENT-SIDE FALLBACK ROUTE\n# ============================================================"
if spa_marker not in content:
    raise RuntimeError("SPA marker not found in ai_backend.py")

suffix = spa_marker + content.split(spa_marker)[1]

with open(NEW_ENDPOINTS_FILE, "r", encoding="utf-8") as f:
    new_endpoints = f.read()

full_content = prefix + new_endpoints + "\n\n" + suffix

with open(BACKEND_FILE, "w", encoding="utf-8") as f:
    f.write(full_content)

print("Merged backend/ai_backend.py successfully!")

