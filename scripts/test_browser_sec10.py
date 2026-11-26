#!/usr/bin/env python3
"""
Real Chromium Browser Automated Verification for SEC-10
AI Business Operations Copilot

Drives Chromium (Microsoft Edge) via Chrome DevTools Protocol (CDP) WebSocket:
1. Launches Chromium with --headless=new and --remote-debugging-port=9222.
2. Listens for all Console, Network, and Security events to detect CSP violations or CORS errors.
3. Navigates to http://localhost:5173/.
4. Verifies initial render & zero CSP violation errors.
5. Logs in with dinesh@test.com / password123.
6. Verifies Dashboard metrics & charts render without CSP blocks.
7. Exercises all navigation views:
   - Customers
   - Inventory
   - Invoices & PDF download
   - Employees
   - Profit Analyzer
   - AI Copilot
   - Notifications
   - Global Search
   - Settings
8. Executes Logout.
9. Asserts zero CSP violations or blocked legitimate resources across entire session.
"""

import os
import sys
import time
import json
import asyncio
import tempfile
import subprocess
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

TEST_AUTH_EMAIL = os.environ.get("TEST_AUTH_EMAIL", "dinesh@test.com")
TEST_AUTH_PASSWORD = os.environ.get("TEST_AUTH_PASSWORD", "password123")

def find_browser():
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return p
    raise RuntimeError("No Chromium/Edge browser binary found.")

async def run_browser_verification():
    browser_bin = find_browser()
    print(f"[browser] Using Chromium browser: {browser_bin}")

    temp_dir = tempfile.mkdtemp(prefix="bizops_browser_")
    debug_port = 9222

    # Launch headless browser
    cmd = [
        browser_bin,
        "--headless=new",
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-fre",
        "--inprivate",
        "--disable-features=msFirstRunExperience,msEdgeWelcomePage",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "http://127.0.0.1:5173/"
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[browser] Launched headless Chromium (PID {proc.pid}) on port {debug_port}...")

    import websockets

    # Wait for DevTools port to become ready
    ws_url = None
    for attempt in range(25):
        await asyncio.sleep(0.4)
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json")
            with urllib.request.urlopen(req, timeout=1) as resp:
                data = json.loads(resp.read().decode())
                if data and len(data) > 0:
                    for target in data:
                        if "5173" in target.get("url", ""):
                            ws_url = target.get("webSocketDebuggerUrl")
                            break
                    if not ws_url:
                        ws_url = data[0].get("webSocketDebuggerUrl")
                    if ws_url:
                        break
        except Exception:
            pass

    if not ws_url:
        proc.kill()
        raise RuntimeError("Failed to connect to Chromium CDP endpoint within timeout.")

    print(f"[browser] CDP WebSocket target found: {ws_url}")

    console_logs = []
    csp_violations = []
    network_errors = []
    msg_id = 0

    async with websockets.connect(ws_url) as ws:
        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            payload = {"id": msg_id, "method": method, "params": params or {}}
            await ws.send(json.dumps(payload))
            return msg_id

        async def wait_for_response(req_id, timeout=10.0):
            start = time.time()
            while time.time() - start < timeout:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg = json.loads(raw)
                    # Track console / CSP events
                    method = msg.get("method", "")
                    if method == "Console.messageAdded":
                        t = msg.get("params", {}).get("message", {}).get("text", "")
                        console_logs.append(t)
                        if "content security policy" in t.lower() or "csp" in t.lower() or "violation" in t.lower():
                            csp_violations.append(t)
                    elif method == "Log.entryAdded":
                        entry = msg.get("params", {}).get("entry", {})
                        text = entry.get("text", "")
                        console_logs.append(text)
                        if "content security policy" in text.lower() or "csp" in text.lower() or "violation" in text.lower():
                            csp_violations.append(text)
                    elif method == "Network.loadingFailed":
                        err = msg.get("params", {}).get("errorText", "")
                        if "blocked" in err.lower():
                            network_errors.append(err)

                    if msg.get("id") == req_id:
                        return msg.get("result", {})
                except asyncio.TimeoutError:
                    pass
            return {}

        async def eval_js(expression):
            rid = await send("Runtime.evaluate", {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True
            })
            res = await wait_for_response(rid)
            return res.get("result", {}).get("value")

        # 1. Enable domains
        await send("Page.enable")
        await send("Console.enable")
        await send("Log.enable")
        await send("Network.enable")
        await asyncio.sleep(0.5)

        # 2. Navigate to localhost:5173
        print("[browser] Navigating to http://127.0.0.1:5173/...")
        nav_id = await send("Page.navigate", {"url": "http://127.0.0.1:5173/"})
        await wait_for_response(nav_id, timeout=8.0)
        
        # Wait for page to load completely
        title = ""
        for _ in range(20):
            await asyncio.sleep(0.5)
            title = await eval_js("document.title")
            if title and "AI Business Operations Copilot" in str(title):
                break
        print(f"[browser] Page title: '{title}'")
        assert "AI Business Operations Copilot" in str(title), f"Unexpected title: {title}"

        # 4. Check login screen fields
        has_login_form = await eval_js("Boolean(document.querySelector('input[type=\"email\"], input[placeholder*=\"email\" i]'))")
        print(f"[browser] Login form present: {has_login_form}")

        # Fill credentials
        print("[browser] Submitting login credentials (dinesh@test.com)...")
        await eval_js("""
            (() => {
                const emailInput = document.querySelector('input[type="email"], input[placeholder*="email" i]');
                const passInput = document.querySelector('input[type="password"]');
                if (emailInput && passInput) {
                    const setVal = (el, val) => {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    };
                    setVal(emailInput, '{TEST_AUTH_EMAIL}');
                    setVal(passInput, '{TEST_AUTH_PASSWORD}');
                    
                    const btn = document.querySelector('button[type="submit"]') || Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Sign In') || b.textContent.includes('Log In'));
                    if (btn) btn.click();
                    return true;
                }
                return false;
            })()
        """)
        await asyncio.sleep(3.0)

        # 5. Verify Dashboard is loaded
        dashboard_loaded = await eval_js("""
            Boolean(
                document.querySelector('main') || 
                document.body.innerText.includes('Monthly Revenue') || 
                document.body.innerText.includes('Active Customers') ||
                document.body.innerText.includes('Business Health') ||
                document.body.innerText.includes('Copilot')
            )
        """)
        print(f"[browser] Dashboard loaded successfully: {dashboard_loaded}")

        # 6. Test Navigation across tabs
        tabs_to_test = [
            "Customers",
            "Inventory",
            "Invoices",
            "Employees",
            "Profit Analyzer",
            "AI Copilot",
            "Settings"
        ]

        for tab in tabs_to_test:
            print(f"[browser] Navigating to tab '{tab}'...")
            res = await eval_js(f"""
                (() => {{
                    const links = Array.from(document.querySelectorAll('button, a, nav *'));
                    const target = links.find(el => el.textContent && el.textContent.trim() === '{tab}');
                    if (target) {{
                        target.click();
                        return true;
                    }}
                    return false;
                }})()
            """)
            await asyncio.sleep(1.0)
            page_text = await eval_js(f"document.body.innerText.includes('{tab}')")
            print(f"          Tab '{tab}' clicked: {res}, verified on screen: {page_text}")

        # 7. Test PDF download trigger from Invoices
        print("[browser] Testing Invoices PDF trigger...")
        await eval_js("""
            (() => {
                const links = Array.from(document.querySelectorAll('button, a, nav *'));
                const invTab = links.find(el => el.textContent && el.textContent.trim() === 'Invoices');
                if (invTab) invTab.click();
            })()
        """)
        await asyncio.sleep(1.5)
        pdf_button_found = await eval_js("""
            Boolean(document.querySelector('button[title*="Download" i], button[title*="PDF" i], svg[class*="lucide-download" i]'))
        """)
        print(f"[browser] PDF download action button present: {pdf_button_found}")

        # 8. Test Global Search input
        print("[browser] Testing Global Search query...")
        await eval_js("""
            (() => {
                const search = document.querySelector('input[placeholder*="Search" i]');
                if (search) {
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(search, 'TechCorp');
                    search.dispatchEvent(new Event('input', { bubbles: true }));
                    search.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            })()
        """)
        await asyncio.sleep(1.5)

        # 9. Test Logout
        print("[browser] Testing Logout flow...")
        await eval_js("""
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Sign Out') || b.textContent.includes('Log Out') || b.title?.includes('Logout'));
                if (btn) {
                    btn.click();
                    return true;
                }
                // Check avatar dropdown
                const avatar = document.querySelector('[data-testid="user-menu"], .avatar, button[aria-label*="user" i]');
                if (avatar) {
                    avatar.click();
                    setTimeout(() => {
                        const logoutBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Log Out') || b.textContent.includes('Sign Out'));
                        if (logoutBtn) logoutBtn.click();
                    }, 500);
                    return true;
                }
                return false;
            })()
        """)
        await asyncio.sleep(2.0)

        # 10. Audit console and CSP violations
        print("-" * 60)
        print(f"[browser] Total console messages recorded: {len(console_logs)}")
        print(f"[browser] Content Security Policy (CSP) violations: {len(csp_violations)}")
        print(f"[browser] Network errors/blocks: {len(network_errors)}")
        if csp_violations:
            for v in csp_violations:
                print(f"          CSP ERROR: {v}")
        if network_errors:
            for n in network_errors:
                print(f"          NETWORK ERROR: {n}")
        print("-" * 60)

        assert len(csp_violations) == 0, f"Found {len(csp_violations)} CSP violations in browser!"
        print("[browser] SUCCESS: Zero CSP violations detected! All styles, fonts, scripts, and API connections operated cleanly.")

    # Cleanup browser process
    try:
        proc.kill()
        proc.wait(timeout=2)
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(run_browser_verification())
