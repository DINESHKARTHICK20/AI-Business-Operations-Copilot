import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_backend import app, login_user, UserLoginRequest, get_db
from fastapi import Response, HTTPException
import traceback
import sqlite3

class MockReq:
    class Client:
        host = '127.0.0.1'
    client = Client()

print("=" * 60)
print("TESTING LOGIN_USER ACROSS ALL REGISTERED USERS")
print("=" * 60)

conn = get_db()
cur = conn.cursor()
cur.execute("SELECT id, name, email, password_hash, password, company, biz_type, is_active FROM users")
users = [dict(r) for r in cur.fetchall()]
conn.close()

passwords = {
    "dinesh@test.com": "password123",
    "arun@company.com": "password123",
    "priya@nexus.in": "password123",
    "security.officer@bizops.in": "SecurePassword2026!",
}

for u in users:
    email = u["email"]
    pw = passwords.get(email, "password123")
    print(f"\nTesting User {u['id']} ({email}):")
    req = UserLoginRequest(email=email, password=pw)
    resp = Response()
    try:
        res = login_user(req, MockReq(), resp)
        print(f"  [SUCCESS] Logged in: {res.get('user', {}).get('name')}")
    except HTTPException as he:
        print(f"  [HTTPException {he.status_code}] {he.detail}")
    except Exception as e:
        print(f"  [500 UNHANDLED EXCEPTION] {type(e).__name__}: {e}")
        traceback.print_exc()

print("\n" + "=" * 60)
print("TESTING POTENTIAL 500 TRIGGER SCENARIOS")
print("=" * 60)

# Scenario 1: Case insensitivity or trailing spaces in email
print("\nScenario 1: Email with uppercase and spaces (' Dinesh@Test.com ')")
try:
    res = login_user(UserLoginRequest(email=" Dinesh@Test.com ", password="password123"), MockReq(), Response())
    print("  [SUCCESS]", res["user"]["email"])
except Exception as e:
    print(f"  [FAIL] {type(e).__name__}: {e}")
    traceback.print_exc()

# Scenario 2: Special characters in password (quotes, backslashes, unicode)
print("\nScenario 2: Special characters in password")
try:
    res = login_user(UserLoginRequest(email="dinesh@test.com", password="password'\"\\;--"), MockReq(), Response())
    print("  [UNEXPECTED SUCCESS]")
except HTTPException as he:
    print(f"  [EXPECTED HTTPException {he.status_code}] {he.detail}")
except Exception as e:
    print(f"  [500 UNHANDLED EXCEPTION] {type(e).__name__}: {e}")
    traceback.print_exc()

# Scenario 3: Database locked during login (e.g. concurrent write)
print("\nScenario 3: SQLite locked by concurrent transaction")
lock_conn = sqlite3.connect("backend/ai_bizops.db", timeout=0.1)
lock_conn.execute("BEGIN EXCLUSIVE")
try:
    res = login_user(UserLoginRequest(email="dinesh@test.com", password="password123"), MockReq(), Response())
    print("  [RESULT] Login succeeded despite lock?")
except HTTPException as he:
    print(f"  [HTTPException {he.status_code}] {he.detail}")
except Exception as e:
    print(f"  [500 REPRODUCED!] {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    lock_conn.rollback()
    lock_conn.close()

# Scenario 4: User without company or biz_type
print("\nScenario 4: Null company/biz_type")
try:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET company = NULL, biz_type = NULL WHERE email = 'dinesh@test.com'")
    conn.commit()
    conn.close()
    res = login_user(UserLoginRequest(email="dinesh@test.com", password="password123"), MockReq(), Response())
    print("  [SUCCESS] Handled null company/biz_type:", res["user"])
except Exception as e:
    print(f"  [500 REPRODUCED!] {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET company = 'Dinesh Tech Solutions', biz_type = 'SaaS' WHERE email = 'dinesh@test.com'")
    conn.commit()
    conn.close()

