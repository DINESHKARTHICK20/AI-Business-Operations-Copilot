"""
Probe actual passwords for the test accounts by trying known combinations.
"""
import sqlite3
import bcrypt

KNOWN_PASSWORDS = [
    'test123', 'password', 'password123', 'admin123', 'admin',
    '123456', 'dinesh123', 'arun123', 'priya123', 'bizops2026',
    'bizops123', 'Test@123', 'test@123', 'test1234', 'password1',
    'changeme', 'secret', 'letmein', '12345678', 'qwerty',
]

conn = sqlite3.connect('backend/ai_bizops.db')
c = conn.cursor()
c.execute('SELECT id, name, email, password_hash FROM users ORDER BY id LIMIT 10')
users = c.fetchall()
conn.close()

print(f'Testing {len(users)} users against {len(KNOWN_PASSWORDS)} password candidates...')
print()

for uid, name, email, phash in users:
    if not phash:
        print(f'{email}: NO HASH STORED')
        continue
    found = None
    for pw in KNOWN_PASSWORDS:
        try:
            if phash.startswith(('$2b$', '$2a$', '$2y$')):
                if bcrypt.checkpw(pw.encode('utf-8'), phash.encode('utf-8')):
                    found = pw
                    break
        except Exception:
            pass
    if found:
        print(f'FOUND: {email} -> password = [{found}]')
    else:
        print(f'UNKNOWN: {email} (hash starts: {phash[:20]})')

