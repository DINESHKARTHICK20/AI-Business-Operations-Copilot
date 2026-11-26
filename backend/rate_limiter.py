"""
SEC-08: Persistent and Distributed Rate Limiting (Hardened)
AI Business Operations Copilot - Production Security Architecture

Provides MySQL-backed shared rate limiting for authentication endpoints:
- Distributed synchronization across multiple FastAPI/Uvicorn worker processes
- Atomic counter increments via MySQL INSERT ... ON DUPLICATE KEY UPDATE
- Strict FAIL-CLOSED behavior: returns HTTP 503 if shared storage is unavailable
  (never relies on isolated in-memory counters across workers)
- 3-Tier brute-force defense:
    1. Per IP + Account (5 attempts / 5m)
    2. Distributed Account-Level across multiple IPs (15 attempts / 5m)
    3. Per IP Global (20 attempts / 5m)
- Fixed-length HMAC-SHA256 keyed hashes for all identifiers:
    * Prevents key-length overflow from oversized email/IP inputs
    * Protects privacy by not storing plaintext emails or IPs in rate_limits
- UTC timestamp synchronization with bounded purging (LIMIT 1000)
- RFC 7239 trusted proxy validation (neutralizes X-Forwarded-For spoofing)
- Automatic recovery when MySQL connectivity returns
"""

import os
import hmac
import hashlib
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Set, Tuple, Dict, List
from fastapi import Request, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from backend.database import engine, is_mysql_mode

logger = logging.getLogger("bizops.rate_limiter")

# Dedicated secret salt for rate-limit identifier hashing
RATE_LIMIT_SALT = os.environ.get("RATE_LIMIT_SALT", "bizops_rate_limit_salt_sec08_v2")

# Default trusted proxy IPs (loopback addresses and configured reverse proxies)
DEFAULT_TRUSTED_PROXIES: Set[str] = {
    "127.0.0.1",
    "::1",
    "localhost",
}


# Operational storage ceiling for rate-limit cache (SEC-09)
MAX_RATE_LIMIT_STORAGE_RECORDS = int(os.environ.get("MAX_RATE_LIMIT_STORAGE_RECORDS", "100000"))


class RateLimitStorageError(Exception):
    """Raised when shared rate-limit storage (MySQL) is unavailable or degraded."""
    pass


def get_trusted_proxies() -> Set[str]:
    """Load trusted proxies from environment variable TRUSTED_PROXIES."""
    configured = os.environ.get("TRUSTED_PROXIES", "").strip()
    if not configured:
        return DEFAULT_TRUSTED_PROXIES
    proxies = set(DEFAULT_TRUSTED_PROXIES)
    for p in configured.split(","):
        cleaned = p.strip()
        if cleaned:
            proxies.add(cleaned)
    return proxies


def get_client_ip(request: Request, trusted_proxies: Optional[Set[str]] = None) -> str:
    """
    Securely extract client IP address.

    Security Rule:
    Only inspect X-Forwarded-For if the direct peer connection (request.client.host)
    originates from an explicitly trusted proxy (e.g., local Vite proxy or Nginx).
    If the direct peer is untrusted, X-Forwarded-For is completely ignored to prevent IP spoofing.
    When trusted, the rightmost untrusted IP in the X-Forwarded-For chain is returned.
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"
    trusted = trusted_proxies if trusted_proxies is not None else get_trusted_proxies()

    if direct_ip not in trusted:
        # Direct connection from untrusted client: reject any forwarded header
        return direct_ip

    # Peer is a trusted proxy (e.g. Vite dev server on 127.0.0.1)
    xff = request.headers.get("X-Forwarded-For")
    if not xff:
        return direct_ip

    # Parse comma-separated hops from right to left
    hops = [h.strip() for h in xff.split(",") if h.strip()]
    if not hops:
        return direct_ip

    # Traverse from right to left to find the first untrusted client IP
    for hop in reversed(hops):
        if hop not in trusted:
            return hop

    # If all hops were trusted proxies, return the leftmost client hop
    return hops[0]


def hash_identifier(val: str, prefix: str = "") -> str:
    """
    Produce a deterministic, fixed-length 32-hex-character keyed hash for rate-limit keys.
    Normalizes input, protects against oversized input strings, and prevents
    sensitive identifiers (emails, IPs) from leaking in plaintext in the database.
    """
    normalized = val.strip().lower()
    digest = hmac.new(
        RATE_LIMIT_SALT.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:32]
    if prefix:
        return f"{prefix}:{digest}"
    return digest


def _acquire_alloc_lock(conn, timeout: float = 3.0) -> bool:
    """Acquire MySQL user-level mutex to serialize allocation of new keys when near capacity."""
    if is_mysql_mode():
        try:
            res = conn.execute(text("SELECT GET_LOCK('rate_limit_alloc_mutex', :t)"), {"t": timeout}).scalar()
            return bool(res == 1)
        except Exception:
            return False
    return True


def _release_alloc_lock(conn):
    """Release MySQL user-level allocation mutex."""
    if is_mysql_mode():
        try:
            conn.execute(text("SELECT RELEASE_LOCK('rate_limit_alloc_mutex')"))
        except Exception:
            pass


class DistributedRateLimiter:
    """
    MySQL-backed rate limiter with atomic upsert, bounded cleanup, fixed-length keys,
    and strict FAIL-CLOSED behavior on database storage failure.
    """

    def __init__(
        self,
        prefix: str = "rl",
        max_attempts: int = 5,
        window_seconds: int = 300,
        cleanup_chance: float = 0.02,
        max_storage_records: Optional[int] = None,
    ):
        self.prefix = prefix
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.cleanup_chance = cleanup_chance
        self.max_storage_records = max_storage_records or MAX_RATE_LIMIT_STORAGE_RECORDS

    def _make_key(self, raw_key: str) -> str:
        # Fixed length key: prefix:hash (always <= 64 chars, safely within VARCHAR(191))
        h = hash_identifier(raw_key)
        return f"{self.prefix}:{h}"

    def is_rate_limited(self, raw_key: str, threshold: Optional[int] = None) -> bool:
        """Check if key has exceeded the attempt threshold within the active window."""
        limit = threshold if threshold is not None else self.max_attempts
        full_key = self._make_key(raw_key)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT attempts, expires_at FROM rate_limits "
                        "WHERE rate_key = :key AND expires_at > :now"
                    ),
                    {"key": full_key, "now": now_utc},
                ).fetchone()

                if row:
                    attempts = row[0]
                    return attempts >= limit
                return False
        except Exception as exc:
            logger.critical(
                "Rate limit storage error in is_rate_limited for key %s: %s. Enforcing fail-closed.",
                full_key,
                exc,
            )
            raise RateLimitStorageError(f"Database error in rate limit storage: {exc}") from exc

    def get_remaining_seconds(self, raw_key: str, threshold: Optional[int] = None) -> int:
        """Return seconds until the rate limit expires (0 if not limited or no record)."""
        full_key = self._make_key(raw_key)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT attempts, expires_at FROM rate_limits "
                        "WHERE rate_key = :key AND expires_at > :now"
                    ),
                    {"key": full_key, "now": now_utc},
                ).fetchone()

                if row and (threshold is None or row[0] >= threshold):
                    exp = row[1]
                    rem = int((exp - now_utc).total_seconds())
                    return max(1, rem)
                return 0
        except Exception as exc:
            logger.critical(
                "Rate limit storage error in get_remaining_seconds for key %s: %s. Enforcing fail-closed.",
                full_key,
                exc,
            )
            raise RateLimitStorageError(f"Database error in rate limit storage: {exc}") from exc

    def record_attempt(self, raw_key: str, window_seconds: Optional[int] = None) -> int:
        """
        Atomically records an attempt:
        - If new or expired: sets attempts = 1, resets window.
        - If active window: increments attempts by 1.
        Uses MySQL INSERT ... ON DUPLICATE KEY UPDATE with row-level locks.
        Enforces storage ceiling: rejects allocation of new keys if capacity is exhausted,
        while preserving all active unexpired counters without deletion.
        """
        win = window_seconds or self.window_seconds
        full_key = self._make_key(raw_key)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        exp_utc = now_utc + timedelta(seconds=win)

        try:
            with engine.begin() as conn:
                # 1. Check if the key already exists in storage
                existing_row = conn.execute(
                    text("SELECT attempts, expires_at FROM rate_limits WHERE rate_key = :key"),
                    {"key": full_key}
                ).fetchone()

                # If key does NOT exist, allocating a new row increases storage.
                # Enforce storage ceiling to protect database capacity with race-safe lock:
                if existing_row is None:
                    locked = _acquire_alloc_lock(conn)
                    try:
                        double_check = conn.execute(
                            text("SELECT attempts, expires_at FROM rate_limits WHERE rate_key = :key"),
                            {"key": full_key}
                        ).fetchone()
                        if double_check is None:
                            count_clause = "FOR SHARE" if is_mysql_mode() else ""
                            count = conn.execute(text(f"SELECT COUNT(*) FROM rate_limits {count_clause}")).scalar() or 0
                            if count >= self.max_storage_records:
                                # Attempt to prune expired rows first
                                if is_mysql_mode():
                                    conn.execute(text("DELETE FROM rate_limits WHERE expires_at < :now LIMIT 1000"), {"now": now_utc})
                                else:
                                    conn.execute(
                                        text("DELETE FROM rate_limits WHERE rate_key IN "
                                             "(SELECT rate_key FROM rate_limits WHERE expires_at < :now LIMIT 1000)"),
                                        {"now": now_utc}
                                    )
                                count = conn.execute(text(f"SELECT COUNT(*) FROM rate_limits {count_clause}")).scalar() or 0
                                if count >= self.max_storage_records:
                                    logger.critical(
                                        "Rate limit storage capacity exhausted (%d/%d records). "
                                        "Active counters preserved; rejecting allocation of new key %s.",
                                        count, self.max_storage_records, full_key
                                    )
                                    raise RateLimitStorageError(
                                        f"Rate limit storage capacity exhausted ({count}/{self.max_storage_records}). "
                                        "Unable to allocate new rate-limit key."
                                    )
                    finally:
                        if locked:
                            _release_alloc_lock(conn)

                # 2. Key exists or capacity is available: perform atomic upsert
                if is_mysql_mode():
                    conn.execute(
                        text(
                            """
                            INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                            VALUES (:key, 1, :now, :now, :exp, :now, :now)
                            ON DUPLICATE KEY UPDATE
                                attempts = IF(expires_at <= :now, 1, attempts + 1),
                                first_attempt_at = IF(expires_at <= :now, :now, first_attempt_at),
                                expires_at = IF(expires_at <= :now, :exp, expires_at),
                                last_attempt_at = :now,
                                updated_at = :now;
                            """
                        ),
                        {"key": full_key, "now": now_utc, "exp": exp_utc},
                    )
                else:
                    # SQLite support for development / tests
                    conn.execute(
                        text(
                            """
                            INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                            VALUES (:key, 1, :now, :now, :exp, :now, :now)
                            ON CONFLICT(rate_key) DO UPDATE SET
                                attempts = CASE WHEN expires_at <= :now THEN 1 ELSE attempts + 1 END,
                                first_attempt_at = CASE WHEN expires_at <= :now THEN :now ELSE first_attempt_at END,
                                expires_at = CASE WHEN expires_at <= :now THEN :exp ELSE expires_at END,
                                last_attempt_at = :now,
                                updated_at = :now;
                            """
                        ),
                        {"key": full_key, "now": now_utc, "exp": exp_utc},
                    )

                # Fetch updated attempt count
                val = conn.execute(
                    text("SELECT attempts FROM rate_limits WHERE rate_key = :key"),
                    {"key": full_key},
                ).scalar()

            # Probabilistic bounded cleanup of expired records
            if random.random() < self.cleanup_chance:
                self.cleanup_expired(limit=500)

            return val or 1

        except Exception as exc:
            logger.critical(
                "Rate limit storage error in record_attempt for key %s: %s. Enforcing fail-closed.",
                full_key,
                exc,
            )
            raise RateLimitStorageError(f"Database error in rate limit storage: {exc}") from exc

    def reserve(
        self,
        raw_key: str,
        max_attempts: int,
        window_seconds: Optional[int] = None,
        cost: int = 1
    ) -> Tuple[bool, int, int]:
        """
        Atomically checks and reserves rate limit quota in a single atomic database operation.
        Uses INSERT ... ON DUPLICATE KEY UPDATE to avoid InnoDB gap locks and deadlocks.
        Retries up to 3 times on transient InnoDB deadlock (error 1213).
        - If active and attempts + cost <= max_attempts: increments attempts, returns (True, new_attempts, remaining_seconds).
        - If active and attempts + cost > max_attempts: returns (False, curr_attempts, remaining_seconds).
        - If expired or new: allocates/resets attempts = cost, returns (True, cost, window_seconds).
        Eliminates race conditions between checking and recording attempts across multiple workers.
        """
        win = window_seconds or self.window_seconds
        full_key = self._make_key(raw_key)

        for attempt_i in range(3):
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            exp_utc = now_utc + timedelta(seconds=win)

            try:
                with engine.begin() as conn:
                    # Check capacity if row does not exist
                    row_exists = conn.execute(
                        text("SELECT 1 FROM rate_limits WHERE rate_key = :key"),
                        {"key": full_key}
                    ).scalar()

                    if not row_exists:
                        locked = _acquire_alloc_lock(conn, timeout=10.0)
                        if not locked:
                            raise RateLimitStorageError("Rate limit storage lock contention. Unable to allocate new rate-limit key.")
                        try:
                            dcheck = conn.execute(
                                text("SELECT 1 FROM rate_limits WHERE rate_key = :key"),
                                {"key": full_key}
                            ).scalar()

                            if not dcheck:
                                count_clause = "FOR SHARE" if is_mysql_mode() else ""
                                count = conn.execute(text(f"SELECT COUNT(*) FROM rate_limits {count_clause}")).scalar() or 0
                                if count >= self.max_storage_records:
                                    if is_mysql_mode():
                                        conn.execute(text("DELETE FROM rate_limits WHERE expires_at < :now LIMIT 1000"), {"now": now_utc})
                                    else:
                                        conn.execute(
                                            text("DELETE FROM rate_limits WHERE rate_key IN "
                                                 "(SELECT rate_key FROM rate_limits WHERE expires_at < :now LIMIT 1000)"),
                                            {"now": now_utc}
                                        )
                                    count = conn.execute(text(f"SELECT COUNT(*) FROM rate_limits {count_clause}")).scalar() or 0
                                    if count >= self.max_storage_records:
                                        logger.critical(
                                            "Rate limit storage capacity exhausted (%d/%d records). "
                                            "Active counters preserved; rejecting allocation of new key %s.",
                                            count, self.max_storage_records, full_key
                                        )
                                        raise RateLimitStorageError(
                                            f"Rate limit storage capacity exhausted ({count}/{self.max_storage_records}). "
                                            "Unable to allocate new rate-limit key."
                                        )

                            # Perform insert while holding allocation lock
                            if is_mysql_mode():
                                conn.execute(
                                    text("""
                                        INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                                        VALUES (:key, :cost, :now, :now, :exp, :now, :now)
                                        ON DUPLICATE KEY UPDATE
                                            attempts = IF(expires_at <= :now, :cost, IF(attempts + :cost <= :max_att, attempts + :cost, attempts + 1)),
                                            first_attempt_at = IF(expires_at <= :now, :now, first_attempt_at),
                                            expires_at = IF(expires_at <= :now, :exp, expires_at),
                                            last_attempt_at = :now,
                                            updated_at = :now;
                                    """),
                                    {"key": full_key, "cost": cost, "now": now_utc, "exp": exp_utc, "max_att": max_attempts}
                                )
                            else:
                                conn.execute(
                                    text("""
                                        INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                                        VALUES (:key, :cost, :now, :now, :exp, :now, :now)
                                        ON CONFLICT(rate_key) DO UPDATE SET
                                            attempts = CASE 
                                                WHEN expires_at <= :now THEN :cost 
                                                WHEN attempts + :cost <= :max_att THEN attempts + :cost 
                                                ELSE attempts + 1 
                                            END,
                                            first_attempt_at = CASE WHEN expires_at <= :now THEN :now ELSE first_attempt_at END,
                                            expires_at = CASE WHEN expires_at <= :now THEN :exp ELSE expires_at END,
                                            last_attempt_at = :now,
                                            updated_at = :now;
                                    """),
                                    {"key": full_key, "cost": cost, "now": now_utc, "exp": exp_utc, "max_att": max_attempts}
                                )
                        finally:
                            _release_alloc_lock(conn)
                    else:
                        # Existing key: update without acquiring allocation lock
                        if is_mysql_mode():
                            conn.execute(
                                text("""
                                    INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                                    VALUES (:key, :cost, :now, :now, :exp, :now, :now)
                                    ON DUPLICATE KEY UPDATE
                                        attempts = IF(expires_at <= :now, :cost, IF(attempts + :cost <= :max_att, attempts + :cost, attempts + 1)),
                                        first_attempt_at = IF(expires_at <= :now, :now, first_attempt_at),
                                        expires_at = IF(expires_at <= :now, :exp, expires_at),
                                        last_attempt_at = :now,
                                        updated_at = :now;
                                """),
                                {"key": full_key, "cost": cost, "now": now_utc, "exp": exp_utc, "max_att": max_attempts}
                            )
                        else:
                            conn.execute(
                                text("""
                                    INSERT INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at)
                                    VALUES (:key, :cost, :now, :now, :exp, :now, :now)
                                    ON CONFLICT(rate_key) DO UPDATE SET
                                        attempts = CASE 
                                            WHEN expires_at <= :now THEN :cost 
                                            WHEN attempts + :cost <= :max_att THEN attempts + :cost 
                                            ELSE attempts + 1 
                                        END,
                                        first_attempt_at = CASE WHEN expires_at <= :now THEN :now ELSE first_attempt_at END,
                                        expires_at = CASE WHEN expires_at <= :now THEN :exp ELSE expires_at END,
                                        last_attempt_at = :now,
                                        updated_at = :now;
                                """),
                                {"key": full_key, "cost": cost, "now": now_utc, "exp": exp_utc, "max_att": max_attempts}
                            )

                    row = conn.execute(
                        text("SELECT attempts, expires_at FROM rate_limits WHERE rate_key = :key"),
                        {"key": full_key}
                    ).fetchone()

                    curr_attempts, expires_at = row[0], row[1]
                    rem = max(1, int((expires_at - now_utc).total_seconds()))

                    if curr_attempts <= max_attempts:
                        return True, curr_attempts, rem
                    else:
                        return False, curr_attempts, rem

            except RateLimitStorageError:
                raise
            except Exception as exc:
                err_str = str(exc)
                if "1213" in err_str or "Deadlock" in err_str:
                    time.sleep(0.01 * (attempt_i + 1))
                    continue
                logger.critical(
                    "Rate limit storage error in reserve for key %s: %s. Enforcing fail-closed.",
                    full_key,
                    exc,
                )
                raise RateLimitStorageError(f"Database error in rate limit storage: {exc}") from exc

        # If all 3 deadlock retries failed
        raise RateLimitStorageError(f"Database deadlock persisted in rate limit storage for key {full_key}")

    def reset(self, raw_key: str):
        """Reset rate limit counter on successful authentication."""
        full_key = self._make_key(raw_key)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM rate_limits WHERE rate_key = :key"),
                    {"key": full_key},
                )
        except Exception as exc:
            logger.error("Database error in reset for key %s: %s", full_key, exc)

    def cleanup_expired(self, limit: int = 1000) -> int:
        """
        Bounded cleanup of expired rate-limit rows.
        Uses LIMIT to prevent lock contention and table growth.
        """
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            with engine.begin() as conn:
                if is_mysql_mode():
                    res = conn.execute(
                        text("DELETE FROM rate_limits WHERE expires_at < :now LIMIT :limit"),
                        {"now": now_utc, "limit": limit},
                    )
                else:
                    res = conn.execute(
                        text(
                            "DELETE FROM rate_limits WHERE rate_key IN "
                            "(SELECT rate_key FROM rate_limits WHERE expires_at < :now LIMIT :limit)"
                        ),
                        {"now": now_utc, "limit": limit},
                    )
                return res.rowcount or 0
        except Exception as exc:
            logger.error("Error cleaning up expired rate-limit records: %s", exc)
            return 0

    def enforce_storage_limits(self, max_records: int = 100000, prune_batch: int = 1000) -> int:
        """
        Prunes only expired rate-limit records up to prune_batch.
        Active rate-limit counters are never deleted merely to free capacity.
        """
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            with engine.begin() as conn:
                if is_mysql_mode():
                    res = conn.execute(
                        text("DELETE FROM rate_limits WHERE expires_at < :now LIMIT :prune"),
                        {"now": now_utc, "prune": prune_batch}
                    )
                else:
                    res = conn.execute(
                        text("DELETE FROM rate_limits WHERE rate_key IN "
                             "(SELECT rate_key FROM rate_limits WHERE expires_at < :now LIMIT :prune)"),
                        {"now": now_utc, "prune": prune_batch}
                    )
                return res.rowcount or 0
        except Exception as exc:
            logger.error("Error during rate limit storage cleanup: %s", exc)
            return 0

    def get_status(self, raw_key: str, threshold: Optional[int] = None) -> dict:
        """Return non-sensitive diagnostic info for a rate-limit key."""
        limit = threshold if threshold is not None else self.max_attempts
        full_key = self._make_key(raw_key)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT attempts, expires_at FROM rate_limits "
                        "WHERE rate_key = :key AND expires_at > :now"
                    ),
                    {"key": full_key, "now": now_utc},
                ).fetchone()

                if row:
                    attempts = row[0]
                    exp = row[1]
                    rem = max(0, int((exp - now_utc).total_seconds())) if attempts >= limit else 0
                    return {
                        "attempts": attempts,
                        "limit": limit,
                        "is_blocked": attempts >= limit,
                        "remaining_seconds": rem,
                        "window_seconds": self.window_seconds,
                    }
                return {
                    "attempts": 0,
                    "limit": limit,
                    "is_blocked": False,
                    "remaining_seconds": 0,
                    "window_seconds": self.window_seconds,
                }
        except Exception as exc:
            logger.critical("Database error in get_status for key %s: %s", full_key, exc)
            raise RateLimitStorageError(f"Database error in get_status: {exc}") from exc


# ============================================================
# SPECIALIZED PRODUCTION RATE LIMITERS
# ============================================================

class LoginRateLimiter:
    """
    Three-tier distributed login rate limiter:
    - Tier 1: Per account + IP: 5 attempts in 5 minutes (prevents targeted single-IP brute force)
    - Tier 2: Per account global: 15 attempts in 5 minutes (prevents distributed multi-IP botnet brute force)
    - Tier 3: Per IP global: 20 attempts in 5 minutes (prevents multi-account credential stuffing from one IP)
    """

    def __init__(
        self,
        max_attempts_per_key: int = 5,
        max_attempts_per_account: int = 15,
        max_attempts_per_ip: int = 20,
        window_seconds: int = 300,
    ):
        self.max_attempts_per_key = max_attempts_per_key
        self.max_attempts_per_account = max_attempts_per_account
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds

        self._backend = DistributedRateLimiter(
            prefix="login",
            max_attempts=max_attempts_per_key,
            window_seconds=window_seconds,
        )

    def is_rate_limited(self, key: str) -> bool:
        """Alias for is_rate_limited_key or is_rate_limited_ip depending on key format."""
        if ":" in key:
            return self.is_rate_limited_key(key)
        return self.is_rate_limited_ip(key)

    def is_rate_limited_key(self, key: str) -> bool:
        """Check Tier 1: IP+account combination rate limit."""
        return self._backend.is_rate_limited(f"acc_ip:{key}", threshold=self.max_attempts_per_key)

    def is_rate_limited_account(self, email: str) -> bool:
        """Check Tier 2: Account-level rate limit across all source IPs (distributed botnet defense)."""
        clean_email = email.strip().lower()
        return self._backend.is_rate_limited(f"acc_global:{clean_email}", threshold=self.max_attempts_per_account)

    def is_rate_limited_ip(self, ip: str) -> bool:
        """Check Tier 3: Bare IP rate limit (credential stuffing defense)."""
        return self._backend.is_rate_limited(f"ip:{ip}", threshold=self.max_attempts_per_ip)

    def record_failure(self, key: str) -> int:
        """Record attempt for IP+account key or bare IP key."""
        prefix = "acc_ip" if ":" in key else "ip"
        return self._backend.record_attempt(f"{prefix}:{key}", window_seconds=self.window_seconds)

    def record_attempt(self, key: str) -> int:
        """Alias for record_failure."""
        return self.record_failure(key)

    def record_account_failure(self, email: str) -> int:
        """Record attempt for account-level global key (Tier 2)."""
        clean_email = email.strip().lower()
        return self._backend.record_attempt(f"acc_global:{clean_email}", window_seconds=self.window_seconds)

    def reset(self, key: str):
        """Reset failed login attempts for a key on successful login."""
        prefix = "acc_ip" if ":" in key else "ip"
        self._backend.reset(f"{prefix}:{key}")

    def reset_account(self, email: str):
        """Reset distributed account-level counter on successful login."""
        clean_email = email.strip().lower()
        self._backend.reset(f"acc_global:{clean_email}")

    def get_remaining_seconds(self, key: str) -> int:
        """Return remaining lockout seconds for IP+account or bare IP key."""
        prefix = "acc_ip" if ":" in key else "ip"
        return self._backend.get_remaining_seconds(f"{prefix}:{key}", threshold=None)

    def get_remaining_seconds_account(self, email: str) -> int:
        """Return remaining lockout seconds for distributed account key."""
        clean_email = email.strip().lower()
        return self._backend.get_remaining_seconds(f"acc_global:{clean_email}", threshold=None)

    def get_status(self, key: str, threshold: Optional[int] = None) -> dict:
        """Return non-sensitive diagnostic info for a rate-limit key."""
        prefix = "acc_ip" if ":" in key else "ip"
        limit = threshold if threshold is not None else (
            self.max_attempts_per_key if ":" in key else self.max_attempts_per_ip
        )
        return self._backend.get_status(f"{prefix}:{key}", threshold=limit)

    def get_status_account(self, email: str) -> dict:
        """Return non-sensitive diagnostic info for account global key."""
        clean_email = email.strip().lower()
        return self._backend.get_status(f"acc_global:{clean_email}", threshold=self.max_attempts_per_account)


class SignupRateLimiter:
    """
    Distributed registration rate limiter:
    - Per IP: 15 signup attempts in 5 minutes (prevents registration flooding)
    """

    def __init__(self, max_attempts_per_ip: int = 15, window_seconds: int = 300):
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds
        self._backend = DistributedRateLimiter(
            prefix="signup",
            max_attempts=max_attempts_per_ip,
            window_seconds=window_seconds,
        )

    def is_rate_limited(self, ip: str) -> bool:
        return self._backend.is_rate_limited(f"ip:{ip}", threshold=self.max_attempts_per_ip)

    def record_attempt(self, ip: str) -> int:
        return self._backend.record_attempt(f"ip:{ip}", window_seconds=self.window_seconds)

    def reset(self, ip: str):
        self._backend.reset(f"ip:{ip}")

    def get_remaining_seconds(self, ip: str) -> int:
        return self._backend.get_remaining_seconds(f"ip:{ip}", threshold=self.max_attempts_per_ip)

    def get_status(self, ip: str) -> dict:
        return self._backend.get_status(f"ip:{ip}", threshold=self.max_attempts_per_ip)


# Global instances matching ai_backend.py integration points
login_limiter = LoginRateLimiter(
    max_attempts_per_key=5,
    max_attempts_per_account=15,
    max_attempts_per_ip=20,
    window_seconds=300
)

signup_limiter = SignupRateLimiter(
    max_attempts_per_ip=15,
    window_seconds=300
)


# ============================================================
# RESOURCE RATE LIMITING FOR EXPENSIVE APIS (SEC-09)
# ============================================================

class ResourceRateLimiter:
    """
    MySQL-backed distributed rate limiter for expensive authenticated API operations (SEC-09).
    Enforces per-user and per-tenant resource limits using verified server-side identity (user_id).
    Returns HTTP 429 with Retry-After when limits are exceeded.
    Fails closed with HTTP 503 if MySQL shared storage is unavailable.
    """
    def __init__(
        self,
        resource_name: str,
        max_attempts: int = 30,
        window_seconds: int = 60,
    ):
        self.resource_name = resource_name
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._backend = DistributedRateLimiter(
            prefix=f"res:{resource_name.lower().replace(' ', '_')}",
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )

    def check_and_record(self, user_id: int) -> int:
        """
        Atomically checks and reserves an attempt for the authenticated user_id in a single database transaction.
        Raises HTTPException 429 if the user has exceeded their rate limit.
        Raises HTTPException 503 if storage is unavailable (fail-closed).
        """
        user_key = f"uid:{user_id}"
        try:
            allowed, attempts, remaining = self._backend.reserve(
                user_key,
                max_attempts=self.max_attempts,
                window_seconds=self.window_seconds,
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for {self.resource_name}. Please try again in {max(1, remaining)} seconds.",
                    headers={"Retry-After": str(max(1, remaining))}
                )
            return attempts
        except HTTPException:
            raise
        except RateLimitStorageError as rse:
            logger.critical(
                "Rate limit storage error for %s (user %s): %s. Enforcing fail-closed 503.",
                self.resource_name, user_id, rse
            )
            raise HTTPException(
                status_code=503,
                detail=f"{self.resource_name} service is temporarily unavailable due to database maintenance. Please try again shortly.",
                headers={"Retry-After": "30"}
            )
        except Exception as exc:
            logger.critical(
                "Unexpected error in rate limiter for %s (user %s): %s. Enforcing fail-closed 503.",
                self.resource_name, user_id, exc
            )
            raise HTTPException(
                status_code=503,
                detail=f"{self.resource_name} service is temporarily unavailable. Please try again shortly.",
                headers={"Retry-After": "30"}
            )

    def reset(self, user_id: int):
        user_key = f"uid:{user_id}"
        self._backend.reset(user_key)

    def get_remaining_seconds(self, user_id: int) -> int:
        user_key = f"uid:{user_id}"
        return self._backend.get_remaining_seconds(user_key, threshold=self.max_attempts)

    def get_status(self, user_id: int) -> dict:
        user_key = f"uid:{user_id}"
        return self._backend.get_status(user_key, threshold=self.max_attempts)


# Dedicated Resource Rate Limiters for SEC-09 Protection
copilot_limiter = ResourceRateLimiter(
    resource_name="AI Copilot",
    max_attempts=int(os.environ.get("RL_COPILOT_MAX", "20")),
    window_seconds=60
)

churn_limiter = ResourceRateLimiter(
    resource_name="Churn Prediction",
    max_attempts=int(os.environ.get("RL_CHURN_MAX", "30")),
    window_seconds=60
)

sales_limiter = ResourceRateLimiter(
    resource_name="Sales Forecasting",
    max_attempts=int(os.environ.get("RL_SALES_MAX", "30")),
    window_seconds=60
)

inventory_limiter = ResourceRateLimiter(
    resource_name="Inventory Forecasting",
    max_attempts=int(os.environ.get("RL_INVENTORY_MAX", "30")),
    window_seconds=60
)

health_limiter = ResourceRateLimiter(
    resource_name="Business Health",
    max_attempts=int(os.environ.get("RL_HEALTH_MAX", "30")),
    window_seconds=60
)

action_center_limiter = ResourceRateLimiter(
    resource_name="Action Center",
    max_attempts=int(os.environ.get("RL_ACTION_MAX", "30")),
    window_seconds=60
)

pdf_limiter = ResourceRateLimiter(
    resource_name="Invoice PDF Generation",
    max_attempts=int(os.environ.get("RL_PDF_MAX", "20")),
    window_seconds=60
)

report_limiter = ResourceRateLimiter(
    resource_name="Report Generation",
    max_attempts=int(os.environ.get("RL_REPORT_MAX", "20")),
    window_seconds=60
)

search_limiter = ResourceRateLimiter(
    resource_name="Global Search",
    max_attempts=int(os.environ.get("RL_SEARCH_MAX", "30")),
    window_seconds=60
)

analytics_limiter = ResourceRateLimiter(
    resource_name="Sales Analytics",
    max_attempts=int(os.environ.get("RL_ANALYTICS_MAX", "40")),
    window_seconds=60
)

session_extend_limiter = ResourceRateLimiter(
    resource_name="Session Extension",
    max_attempts=int(os.environ.get("RL_SESSION_EXTEND_MAX", "15")),
    window_seconds=60
)

session_cleanup_limiter = ResourceRateLimiter(
    resource_name="Session Cleanup",
    max_attempts=int(os.environ.get("RL_SESSION_CLEANUP_MAX", "10")),
    window_seconds=60
)


