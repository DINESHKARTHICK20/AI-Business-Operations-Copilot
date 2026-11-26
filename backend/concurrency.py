"""
Distributed Concurrency Manager for AI Business Operations Copilot
SEC-09: Enforces global and per-user concurrency limits across all backend workers using MySQL.

Features:
- Global concurrency limit (default: 16)
- Per-user concurrency limit (default: 4)
- Lease TTL expiration (default: 30s) prevents stale reservations and deadlocks from crashed workers
- Atomic slot reservation with table lock / mutex
- Graceful release on completion, exception, or cancellation
- Process-local BoundedSemaphore as fast secondary safeguard
- No Redis or Docker required.
"""

import os
import time
import uuid
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from fastapi import HTTPException
from sqlalchemy import text
from backend.database import engine, is_mysql_mode

logger = logging.getLogger("bizops.concurrency")

# Process-local secondary safeguard semaphore
MAX_LOCAL_CONCURRENCY = int(os.environ.get("CONCURRENCY_LOCAL_MAX", "16"))
local_process_semaphore = threading.BoundedSemaphore(value=MAX_LOCAL_CONCURRENCY)

# Global thread pool for bounded sync execution
execution_pool = ThreadPoolExecutor(max_workers=32, thread_name_prefix="bizops_worker")


def init_concurrency_table(engine_instance=None):
    """Ensure concurrency_leases table exists (SQLite fallback mode only)."""
    if is_mysql_mode():
        # In MySQL mode, schema is managed strictly by Alembic migrations (revision 005)
        return
    eng = engine_instance or engine
    try:
        with eng.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS concurrency_leases (
                    lease_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    worker_pid INTEGER NOT NULL,
                    worker_host TEXT NOT NULL,
                    acquired_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conc_res_user ON concurrency_leases (resource_type, user_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conc_expires ON concurrency_leases (expires_at);"))
    except Exception as exc:
        logger.warning("Could not auto-create concurrency_leases table in fallback mode: %s", exc)


# Initialize table on module load
try:
    init_concurrency_table()
except Exception as e:
    logger.debug("Deferred concurrency table init: %s", e)


class DistributedConcurrencyGuard:
    """
    Context manager enforcing distributed concurrency across multiple backend workers
    backed by MySQL table concurrency_leases.
    """
    def __init__(
        self,
        resource_type: str = "expensive_op",
        user_id: int = 0,
        global_limit: Optional[int] = None,
        user_limit: Optional[int] = None,
        acquire_timeout: Optional[float] = None,
        lease_ttl: Optional[float] = None,
        op_name: str = "expensive operation",
        timeout: Optional[float] = None,
    ):
        self.resource_type = resource_type
        self.user_id = int(user_id) if user_id else 0
        self.global_limit = global_limit or int(os.environ.get("CONCURRENCY_GLOBAL_LIMIT", "16"))
        self.user_limit = user_limit or int(os.environ.get("CONCURRENCY_USER_LIMIT", "4"))
        eff_timeout = acquire_timeout if acquire_timeout is not None else (timeout if timeout is not None else 5.0)
        self.acquire_timeout = eff_timeout
        self.lease_ttl = lease_ttl or float(os.environ.get("CONCURRENCY_LEASE_TTL", "30.0"))
        self.op_name = op_name
        self.lease_id = str(uuid.uuid4())
        self.acquired = False
        self.local_acquired = False
        self._retained = False
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self.pid = os.getpid()
        self.host = "localhost"

    def _start_heartbeat(self):
        """Starts a background heartbeat thread to renew the lease TTL while active."""
        self._stop_heartbeat.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"lease_hb_{self.lease_id[:8]}",
            daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat_loop(self):
        """Stops the heartbeat renewal thread."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            try:
                self._heartbeat_thread.join(timeout=1.0)
            except Exception:
                pass
        self._heartbeat_thread = None

    def _heartbeat_loop(self):
        """Periodically pushes lease expiration forward to prevent premature expiration."""
        renewal_interval = max(0.5, self.lease_ttl / 3.0)
        while not self._stop_heartbeat.wait(timeout=renewal_interval):
            if not self.acquired:
                break
            try:
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                new_exp = now_utc + timedelta(seconds=self.lease_ttl)
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE concurrency_leases SET expires_at = :new_exp WHERE lease_id = :lid"),
                        {"new_exp": new_exp, "lid": self.lease_id}
                    )
                logger.debug("Renewed concurrency lease %s until %s", self.lease_id, new_exp)
            except Exception as exc:
                logger.warning("Error renewing lease %s: %s", self.lease_id, exc)

    def release_now(self):
        """Immediately stops renewal, deletes the lease, and releases concurrency capacity."""
        self._stop_heartbeat_loop()
        if self.acquired:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM concurrency_leases WHERE lease_id = :lid"),
                        {"lid": self.lease_id}
                    )
            except Exception as exc:
                logger.error("Error releasing distributed concurrency lease %s: %s", self.lease_id, exc)
            self.acquired = False

        if self.local_acquired:
            try:
                local_process_semaphore.release()
            except ValueError:
                pass
            self.local_acquired = False

    def retain_for_future(self, future):
        """
        Retains this lease for a timed-out computation that is still actively running.
        The lease continues renewing until the future terminates, ensuring the slot
        is NOT released prematurely to other requests.
        """
        self._retained = True
        logger.warning(
            "Retaining concurrency lease %s for running timed-out computation (%s).",
            self.lease_id, self.op_name
        )

        def _supervisor():
            try:
                # Wait for running future to actually complete (or max 120s safety ceiling)
                future.result(timeout=120.0)
            except Exception:
                pass
            finally:
                logger.info("Running timed-out operation %s terminated; releasing retained lease.", self.op_name)
                self.release_now()

        t = threading.Thread(target=_supervisor, name=f"retain_{self.lease_id[:8]}", daemon=True)
        t.start()

    def __enter__(self):
        start_time = time.time()
        deadline = start_time + self.acquire_timeout

        # 1. Process-local fast semaphore
        rem_local = max(0.01, deadline - time.time())
        self.local_acquired = local_process_semaphore.acquire(timeout=rem_local)
        if not self.local_acquired:
            logger.warning(
                "Process-local concurrency saturation (%d) reached for %s",
                MAX_LOCAL_CONCURRENCY, self.op_name
            )
            raise HTTPException(
                status_code=503,
                detail=f"Server is currently experiencing high load for {self.op_name}. Please retry shortly.",
                headers={"Retry-After": "5"}
            )

        # 2. Distributed MySQL lease acquisition
        while time.time() < deadline:
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            exp_utc = now_utc + timedelta(seconds=self.lease_ttl)

            try:
                with engine.begin() as conn:
                    # In MySQL, serialize checking and reservation using advisory lock
                    if is_mysql_mode():
                        conn.execute(text("SELECT GET_LOCK('concurrency_lease_mutex', 2)"))

                    try:
                        # Purge stale/expired leases (from crashed workers or dead hosts)
                        conn.execute(
                            text("DELETE FROM concurrency_leases WHERE expires_at < :now"),
                            {"now": now_utc}
                        )

                        # Check global concurrency
                        global_count = conn.execute(
                            text("SELECT COUNT(*) FROM concurrency_leases WHERE resource_type = :res"),
                            {"res": self.resource_type}
                        ).scalar() or 0

                        # Check per-user concurrency
                        user_count = 0
                        if self.user_id > 0:
                            user_count = conn.execute(
                                text("SELECT COUNT(*) FROM concurrency_leases WHERE resource_type = :res AND user_id = :uid"),
                                {"res": self.resource_type, "uid": self.user_id}
                            ).scalar() or 0

                        if global_count < self.global_limit and (self.user_id == 0 or user_count < self.user_limit):
                            # Slot available: allocate lease
                            conn.execute(
                                text("""
                                    INSERT INTO concurrency_leases
                                    (lease_id, resource_type, user_id, worker_pid, worker_host, acquired_at, expires_at, created_at)
                                    VALUES (:lid, :res, :uid, :pid, :host, :now, :exp, :now)
                                """),
                                {
                                    "lid": self.lease_id,
                                    "res": self.resource_type,
                                    "uid": self.user_id,
                                    "pid": self.pid,
                                    "host": self.host,
                                    "now": now_utc,
                                    "exp": exp_utc,
                                }
                            )
                            self.acquired = True
                            self._start_heartbeat()
                            return self
                    finally:
                        if is_mysql_mode():
                            conn.execute(text("SELECT RELEASE_LOCK('concurrency_lease_mutex')"))

            except HTTPException:
                raise
            except Exception as exc:
                logger.error("Error acquiring distributed concurrency lease: %s", exc)

            time.sleep(0.05)

        # Timed out waiting for distributed slot
        if self.local_acquired:
            local_process_semaphore.release()
            self.local_acquired = False

        logger.warning(
            "Distributed concurrency limit reached for %s (global: %d, user %d: %d). Timed out after %.1fs",
            self.op_name, self.global_limit, self.user_id, self.user_limit, self.acquire_timeout
        )
        raise HTTPException(
            status_code=503,
            detail=f"Server is currently experiencing high load for {self.op_name}. Please retry shortly.",
            headers={"Retry-After": "5"}
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._retained:
            # Lease ownership delegated to supervisor thread until computation actually finishes
            return
        self.release_now()


def run_with_execution_timeout(
    func: Callable,
    *args,
    timeout_seconds: float = 10.0,
    op_name: str = "Operation",
    guard: Optional[DistributedConcurrencyGuard] = None,
    cancel_token: Optional[threading.Event] = None,
    **kwargs
) -> Any:
    """
    Executes func with a strict deadline using a worker thread.
    - If execution exceeds timeout_seconds:
      - Signals cancel_token (if provided) for cooperative termination.
      - If guard is associated and thread is still running, retains lease/slot until termination.
      - Raises HTTPException 504.
    """
    future = execution_pool.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        logger.warning("Operation '%s' exceeded execution deadline of %.1fs", op_name, timeout_seconds)
        if cancel_token is not None:
            cancel_token.set()
        if guard is not None and future.running():
            guard.retain_for_future(future)
        raise HTTPException(
            status_code=504,
            detail=f"Operation timed out: {op_name} exceeded execution deadline of {timeout_seconds}s."
        )


def purge_all_leases():
    """Purge all concurrency leases (used in cleanup/tests)."""
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM concurrency_leases"))
    except Exception as e:
        logger.warning("Purge leases warning: %s", e)
