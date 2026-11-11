"""
Comprehensive final diagnostic test using correct passwords.
"""
import subprocess, time, urllib.request, json, urllib.error, sys, os, random, threading

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Start server
proc = subprocess.Popen(
    [r'.venv\Scripts\python.exe', '-m', 'uvicorn', 'main:app',
     '--host', '127.0.0.1', '--port', '8000', '--log-level', 'warning'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
)
print("Server started, PID:", proc.pid)
time.sleep(7)

if proc.poll() is not None:
    out, err = proc.communicate()
    print("SERVER FAILED TO START:")
    print(err.decode(errors='replace'))
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
    status = 'PASS' if condition else 'FAIL'
    print(f'  {status}: {label}' + (f' | {detail}' if not condition else ''))
    if condition:
        passed += 1
    else:
        failed += 1


print()
print('=== HEALTH ===')
c, b = get(base + '/health')
check('Health 200', c == 200, f'got {c}')
check('DB connected', isinstance(b, dict) and b.get('database') == 'connected', str(b))

print()
print('=== LOGIN: dinesh@test.com / password123 ===')
c, b, hdrs = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'password123'})
print(f'  Status: {c}, user: {b.get("user") if isinstance(b,dict) else b}')
check('Login 200', c == 200, f'{c}: {b}')
check('Has user', isinstance(b, dict) and 'user' in b, str(b))
check('No 500 error', c != 500, f'got 500')
token_dinesh = b.get('token', '') if isinstance(b, dict) else ''

print()
print('=== LOGIN: arun@company.com / password123 ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'arun@company.com', 'password': 'password123'})
print(f'  Status: {c}')
check('Login 200', c == 200, f'{c}: {b}')

print()
print('=== LOGIN: priya@nexus.in / password123 ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'priya@nexus.in', 'password': 'password123'})
print(f'  Status: {c}')
check('Login 200', c == 200, f'{c}: {b}')

print()
print('=== WRONG PASSWORD -> must be 401, not 500 ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'wrongpass'})
check('Wrong pw = 401', c == 401, f'got {c}')
check('Not 500', c != 500, f'got {c}')

print()
print('=== USER WITH NO HASH (ssmc@gmail.com) -> must be 401, not 500 ===')
c, b, _ = post(base + '/api/auth/login', {'email': 'ssmc@gmail.com', 'password': 'anypassword'})
print(f'  Status: {c}, detail: {b.get("detail") if isinstance(b,dict) else b}')
check('No-hash user = 401 (not 500)', c in (401, 400), f'got {c}: {b}')

print()
print('=== ME ENDPOINT ===')
if token_dinesh:
    c, b = get(base + '/api/auth/me', f'session_token={token_dinesh}')
    check('Me 200', c == 200, f'{c}: {b}')
    check('Me has email', isinstance(b, dict) and b.get('email') == 'dinesh@test.com', str(b))

print()
print('=== REGISTER + LOGIN ===')
uid = random.randint(10000, 99999)
test_email = f'diag{uid}@example.com'
c, b, _ = post(base + '/api/auth/register', {'name': 'Diag User', 'email': test_email, 'password': 'diagpass123'})
check('Register 200', c == 200, f'{c}: {b}')
c, b, _ = post(base + '/api/auth/login', {'email': test_email, 'password': 'diagpass123'})
check('New user login 200', c == 200, f'{c}: {b}')

print()
print('=== LOGOUT + ME AFTER LOGOUT ===')
if token_dinesh:
    c, b, _ = post(base + '/api/auth/logout', {}, f'session_token={token_dinesh}')
    check('Logout 200', c == 200, f'{c}')
    c, b = get(base + '/api/auth/me', f'session_token={token_dinesh}')
    check('Me after logout = 401', c == 401, f'got {c}')

print()
print('=== CONCURRENT LOGINS (8 parallel) ===')
concurrent_results = []


def conc_login():
    cc, bb, _ = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'password123'})
    concurrent_results.append(cc)


threads = [threading.Thread(target=conc_login) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f'  Results: {concurrent_results}')
check('All concurrent 200', all(r == 200 for r in concurrent_results), str(concurrent_results))
check('No 500s in concurrent', all(r != 500 for r in concurrent_results), str(concurrent_results))

print()
print('=== PAGE REFRESH: re-login after restart simulation ===')
# Kill server, restart it, login again
proc.terminate()
proc.wait(timeout=5)
proc2 = subprocess.Popen(
    [r'.venv\Scripts\python.exe', '-m', 'uvicorn', 'main:app',
     '--host', '127.0.0.1', '--port', '8000', '--log-level', 'warning'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
)
time.sleep(7)
c, b, _ = post(base + '/api/auth/login', {'email': 'dinesh@test.com', 'password': 'password123'})
check('Login after restart 200', c == 200, f'{c}: {b}')
proc2.terminate()
proc2.wait(timeout=5)

print()
print(f'=== SUMMARY: {passed} passed, {failed} failed ===')
sys.exit(0 if failed == 0 else 1)

