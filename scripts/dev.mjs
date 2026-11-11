import { spawn, execSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 5173;

function getAllPidsOnPort(port) {
  const pids = [];
  try {
    const out = execSync('netstat -ano -p tcp', { encoding: 'utf8' });
    for (const line of out.split('\n')) {
      if (line.includes(`:${port}`) && line.includes('LISTENING')) {
        const parts = line.trim().split(/\s+/);
        const pid = parseInt(parts[parts.length - 1], 10);
        if (pid && !isNaN(pid) && pid > 4 && pid !== process.pid && !pids.includes(pid)) {
          pids.push(pid);
        }
      }
    }
  } catch {}
  return pids;
}

function killPid(pid) {
  if (!pid || pid <= 4) return;
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /F /T /PID ${pid}`, { stdio: 'ignore' });
    } else {
      process.kill(pid, 'SIGKILL');
    }
  } catch {}
}

function freePort(port) {
  const pids = getAllPidsOnPort(port);
  for (const pid of pids) {
    killPid(pid);
  }
}

function findPython() {
  const venvPythonWin = path.join(rootDir, '.venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPythonWin)) {
    return venvPythonWin;
  }
  const venvPythonUnix = path.join(rootDir, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPythonUnix)) {
    return venvPythonUnix;
  }
  return 'python';
}

function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, { timeout: 1500 }, (res) => {
      if (res.statusCode === 200) {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            if (json && json.status === 'healthy') {
              return resolve(true);
            }
          } catch {}
          resolve(false);
        });
      } else {
        resolve(false);
      }
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

async function waitForBackendReady(timeoutMs = 60000) {
  const start = Date.now();
  process.stdout.write(`[dev] Waiting for FastAPI backend to load ML models & bind port ${BACKEND_PORT}...`);
  while (Date.now() - start < timeoutMs) {
    const ready = await checkBackendHealth();
    if (ready) {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      process.stdout.write(` ready in ${elapsed}s!\n`);
      return true;
    }
    process.stdout.write('.');
    await new Promise((r) => setTimeout(r, 400));
  }
  process.stdout.write(' TIMED OUT!\n');
  return false;
}

let backendProc = null;
let viteProc = null;
let isExiting = false;

function cleanupAndExit() {
  if (isExiting) return;
  isExiting = true;
  console.log('\n[dev] Stopping AI Business Operations Copilot...');

  if (viteProc && viteProc.pid) {
    killPid(viteProc.pid);
  }
  if (backendProc && backendProc.pid) {
    killPid(backendProc.pid);
  }

  // Double check no orphan process left on ports
  freePort(BACKEND_PORT);
  freePort(FRONTEND_PORT);

  process.exit(0);
}

process.on('SIGINT', cleanupAndExit);
process.on('SIGTERM', cleanupAndExit);
process.on('exit', cleanupAndExit);

async function main() {
  console.log('============================================================');
  console.log(' AI Business Operations Copilot — Unified Startup Runner');
  console.log(' URL: http://localhost:5173/');
  console.log('============================================================');

  // 1. Prevent duplicate backend processes and port conflicts
  freePort(BACKEND_PORT);
  freePort(FRONTEND_PORT);
  await new Promise((r) => setTimeout(r, 400));

  // 2. Start Python FastAPI backend
  const pythonPath = findPython();
  console.log(`[dev] Starting FastAPI backend using: ${pythonPath}`);
  backendProc = spawn(pythonPath, ['-u', 'main.py'], {
    cwd: rootDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  backendProc.stdout.on('data', (data) => {
    process.stdout.write(`[backend] ${data}`);
  });

  backendProc.stderr.on('data', (data) => {
    process.stderr.write(`[backend] ${data}`);
  });

  backendProc.on('exit', (code) => {
    if (!isExiting && code !== 0) {
      console.error(`[backend] FastAPI backend exited unexpectedly with code ${code}`);
      cleanupAndExit();
    }
  });

  // 3. Ensure backend is fully ready before starting Vite & accepting traffic
  const ready = await waitForBackendReady(60000);
  if (!ready) {
    console.error('[dev] ERROR: Backend failed to report healthy status within timeout.');
    cleanupAndExit();
    return;
  }

  console.log('[dev] FastAPI backend verified healthy & connected to SQLite database.');

  // 4. Start Vite frontend server
  console.log(`[dev] Starting Vite dev server on http://localhost:${FRONTEND_PORT}/...`);
  const viteBin = path.join(rootDir, 'node_modules', 'vite', 'bin', 'vite.js');
  viteProc = spawn(process.execPath, [viteBin, '--host', '127.0.0.1', '--port', String(FRONTEND_PORT)], {
    cwd: rootDir,
    stdio: 'inherit',
    windowsHide: false,
  });

  viteProc.on('exit', (code) => {
    if (!isExiting) {
      cleanupAndExit();
    }
  });
}

main().catch((err) => {
  console.error('[dev] Startup error:', err);
  cleanupAndExit();
});

