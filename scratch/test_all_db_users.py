import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from backend.ai_backend import login_user, UserLoginRequest, get_db
from fastapi import Response

class MockReq:
    class Client:
        host = '127.0.0.1'
    client = Client()

conn = get_db()
cur = conn.cursor()
cur.execute('SELECT id, email, password, password_hash FROM users')
users = cur.fetchall()
conn.close()

print(f"Testing {len(users)} users in DB...")
for u in users:
    uid = u['id']
    email = u['email']
    print(f"User {uid}: {email}")
    req = UserLoginRequest(email=email, password='password123')
    resp = Response()
    try:
        res = login_user(req, MockReq(), resp)
        print(f"  -> Success: {res['status']}")
    except Exception as e:
        print(f"  -> Error ({type(e).__name__}): {e}")
