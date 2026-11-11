"""
Live backend diagnostic test.
Starts the server, runs all auth tests, then terminates.
"""
import subprocess, time, urllib.request, json, urllib.error, sys, os, random

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Start server
proc = subprocess.Popen(
    [r'.venv\Scripts\python.exe', '-m', 'uvicorn', 'main:app',
     '--host', '127.0.0.1', '--port', '8000', '--log-level', 'debug'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
)
print("Server started, PID:", proc.pid)
time.sleep(7)

# Check if server is still running
if proc.poll() is not None:
    out, err = proc.communicate()
    print("SERVER FAILED TO START:")
    print("stdout:", out.decode(errors='replace'))
    print("stderr:", err.decode(errors='replace'))
    sys.exit(1)


def post(url, data, cookies=''):
    body = json.dumps(data).encode()
    headers = {'Content-Type': 'application/json'}
    if cookies:
        headers['Cookie'] = cookies
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            hdrs = dict(resp.headers)
            return resp.status, json.loads(resp.read()), hdrs
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes), {}
        except Exception:
            return e.code, {'raw': body_bytes.decode(errors='replace')}, {}
    except Exception as ex:
        return 0, str(ex), {}


def get(url, cookies=''):
    headers = {}
    if cookies:
        headers['Cookie'] = cookies
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as ex:
        return 0, str(ex)


base = 'http://127.0.0.1:8000'
passed = 0
failed = 0

def check(label, condition, detail=''):
    global passed, failed
    if condition:
        print(f'  PASS: {label}')
        passed += 1
    else:
        print(f'  FAIL: {label} | {detail}')
        failed += 1


print()
print('=== HEALTH CHECK ===')
c, b = get(base + '/health')
print(f'  Status: {c}, body: {b}')
check('Health 200', c == 200, f'got {c}')
check('DB connected', isinstance(b, dict) and b.get('database') == 'connected', str(b))

print()
print('=== LOGIN: dinesh@test.com ===')
c, b, hdrs = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'test123'})
print(f'  Status: {c}')
print(f'  Body: {b}')
check('Login 200', c == 200, f'got {c}: {b}')
check('Has user object', isinstance(b, dict) and 'user' in b, str(b))
token_dinesh = b.get('token', '') if isinstance(b, dict) else ''

print()
print('=== WRONG PASSWORD ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'wrongpassword'})
print(f'  Status: {c}, detail: {b.get("detail") if isinstance(b, dict) else b}')
check('Wrong password = 401', c == 401, f'got {c}')

print()
print('=== NONEXISTENT USER ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'nobody@nowhere.com', 'password': 'test123'})
print(f'  Status: {c}, detail: {b.get("detail") if isinstance(b, dict) else b}')
check('Unknown user = 401', c == 401, f'got {c}')

print()
print('=== EMPTY CREDENTIALS ===')
c, b, _ = post(base + '/api/auth/login', {'email': '', 'password': ''})
print(f'  Status: {c}, detail: {b.get("detail") if isinstance(b, dict) else b}')
check('Empty creds = 400', c == 400, f'got {c}')

print()
print('=== REGISTER NEW USER ===')
uid = random.randint(10000, 99999)
test_email = f'testlive{uid}@example.com'
c, b, _ = post(base + '/api/auth/register', {'name': 'Test Live', 'email': test_email, 'password': 'testlive123'})
print(f'  Status: {c}, body: {b}')
check('Register 200', c == 200, f'got {c}: {b}')

print()
print('=== LOGIN REGISTERED USER ===')
c, b, _ = post(base + '/api/auth/login', {'email': test_email, 'password': 'testlive123'})
print(f'  Status: {c}, body: {b}')
check('New user login 200', c == 200, f'got {c}: {b}')

print()
print('=== DUPLICATE REGISTRATION ===')
c, b, _ = post(base + '/api/auth/register', {'name': 'Test Live Dup', 'email': test_email, 'password': 'duppass123'})
print(f'  Status: {c}, detail: {b.get("detail") if isinstance(b, dict) else b}')
check('Duplicate = 400', c == 400, f'got {c}')

print()
print('=== /api/auth/me WITH SESSION TOKEN ===')
if token_dinesh:
    c, b = get(base + '/api/auth/me', f'session_token={token_dinesh}')
    print(f'  Status: {c}, body: {b}')
    check('Me 200', c == 200, f'got {c}: {b}')
    check('Me returns email', isinstance(b, dict) and 'email' in b, str(b))
else:
    print('  SKIP (no token)')

print()
print('=== LOGOUT ===')
if token_dinesh:
    c, b, _ = post(base + '/api/auth/logout', {}, f'session_token={token_dinesh}')
    print(f'  Status: {c}, body: {b}')
    check('Logout 200', c == 200, f'got {c}: {b}')

print()
print('=== /api/auth/me AFTER LOGOUT ===')
if token_dinesh:
    c, b = get(base + '/api/auth/me', f'session_token={token_dinesh}')
    print(f'  Status: {c}')
    check('Me after logout = 401', c == 401, f'got {c}: {b}')

print()
print('=== CONCURRENT LOGINS (5 parallel) ===')
import threading
results = []
def concurrent_login():
    cc, bb, _ = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'test123'})
    results.append(cc)

threads = [threading.Thread(target=concurrent_login) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print(f'  Results: {results}')
check('All concurrent logins succeed', all(r == 200 for r in results), str(results))

print()
print(f'=== SUMMARY: {passed} passed, {failed} failed ===')

proc.terminate()
try:
    proc.wait(timeout=3)
except Exception:
    proc.kill()

sys.exit(0 if failed == 0 else 1)

