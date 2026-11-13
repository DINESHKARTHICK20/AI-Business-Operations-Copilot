import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import ai_backend
from ai_backend import get_db, verify_password, hash_password, login_user, UserLoginRequest

print("Testing direct DB query...")
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT id, email, password_hash FROM users WHERE email='dinesh@test.com'")
row = cur.fetchone()
print(f"Row: {dict(row)}")
pw_hash = row["password_hash"]

print("Testing verify_password('password123', pw_hash)...")
match = verify_password("password123", pw_hash)
print(f"Password match: {match}")

conn.close()

