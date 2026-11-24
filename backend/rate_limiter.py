"""
SEC-08: Persistent and Distributed Rate Limiting
AI Business Operations Copilot - Production Security Architecture

Provides MySQL-backed shared rate limiting for authentication endpoints:
- Distributed synchronization across multiple FastAPI/Uvicorn worker processes
- Atomic counter increments via MySQL INSERT ... ON DUPLICATE KEY UPDATE
- Sliding window expiration handling using UTC timestamps
- Bounded cleanup of expired entries with index acceleration
- Trusted proxy verification (RFC 7239 compliant; prevents X-Forwarded-For spoofing)
- Fail-secure fallback: continues enforcing limits in-memory if database is degraded
- 100% backward compatible API for LoginRateLimiter and SignupRateLimiter
"""

import os
import time
import random
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Set, Tuple, Dict, List
from fastapi import Request
from sqlalchemy import text

from backend.database import engine, is_mysql_mode

logger = logging.getLogger("bizops.rate_limiter")

# Default trusted proxy IPs (loopback addresses and configured reverse proxies)
DEFAULT_TRUSTED_PROXIES: Set[str] = {
    "127.0.0.1",
    "::1",
    "localhost",
    "testclient",
}


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


class DistributedRateLimiter:
    """
    MySQL-backed rate limiter with atomic upsert, bounded cleanup, and fail-secure fallback.
    """

    def __init__(
        self,
        prefix: str = "rl",
        max_attempts: int = 5,
        window_seconds: int = 300,
        cleanup_chance: float = 0.02,
    ):
        self.prefix = prefix
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.cleanup_chance = cleanup_chance

        # Fail-secure in-memory fallback for transient DB failures
        self._fallback_lock = threading.Lock()
        self._fallback_attempts: Dict[str, List[float]] = {}

    def _make_key(self, raw_key: str) -> str:
        return f"{self.prefix}:{raw_key}"[:190]

    def _fallback_check(self, key: str, threshold: int) -> Tuple[bool, int, int]:
        """In-memory check used strictly during database outages."""
        now = time.time()
        with self._fallback_lock:
            if key in self._fallback_attempts:
                self._fallback_attempts[key] = [
                    t for t in self._fallback_attempts[key] if now - t < self.window_seconds
                ]
                if not self._fallback_attempts[key]:
                    del self._fallback_attempts[key]
            timestamps = self._fallback_attempts.get(key, [])
            count = len(timestamps)
            if count >= threshold:
                oldest = min(timestamps)
                rem = max(1, int(self.window_seconds - (now - oldest)))
                return True, rem, count
            return False, 0, count

    def _fallback_record(self, key: str):
        """In-memory record used strictly during database outages."""
        now = time.time()
        with self._fallback_lock:
            if key not in self._fallback_attempts:
                self._fallback_attempts[key] = []
            self._fallback_attempts[key].append(now)

    def _fallback_reset(self, key: str):
        with self._fallback_lock:
            self._fallback_attempts.pop(key, None)

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
            logger.error(
                "Database error in is_rate_limited for key %s: %s. Engaging fail-secure fallback.",
                full_key,
                exc,
            )
            blocked, _, _ = self._fallback_check(full_key, limit)
            return blocked

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
            logger.error(
                "Database error in get_remaining_seconds for key %s: %s. Using fail-secure fallback.",
                full_key,
                exc,
            )
            limit = threshold if threshold is not None else self.max_attempts
            _, rem, _ = self._fallback_check(full_key, limit)
            return rem

    def record_attempt(self, raw_key: str, window_seconds: Optional[int] = None) -> int:
        """
        Atomically records an attempt:
        - If new or expired: sets attempts = 1, resets window.
        - If active window: increments attempts by 1.
        Uses MySQL INSERT ... ON DUPLICATE KEY UPDATE with row-level locks.
        """
        win = window_seconds or self.window_seconds
        full_key = self._make_key(raw_key)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        exp_utc = now_utc + timedelta(seconds=win)

        try:
            with engine.begin() as conn:
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
            logger.error(
                "Database error in record_attempt for key %s: %s. Using fail-secure fallback.",
                full_key,
                exc,
            )
            self._fallback_record(full_key)
            _, _, count = self._fallback_check(full_key, self.max_attempts)
            return count

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
        finally:
            self._fallback_reset(full_key)

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
            logger.error("Database error in get_status for key %s: %s", full_key, exc)
            blocked, rem, count = self._fallback_check(full_key, limit)
            return {
                "attempts": count,
                "limit": limit,
                "is_blocked": blocked,
                "remaining_seconds": rem,
                "window_seconds": self.window_seconds,
            }


# ============================================================
# SPECIALIZED PRODUCTION RATE LIMITERS
# ============================================================

class LoginRateLimiter:
    """
    Two-tier distributed login rate limiter:
    - Per account + IP (rate_key): 5 attempts in 5 minutes (prevents brute-force on single account)
    - Per IP (client_ip): 20 attempts in 5 minutes (prevents credential-stuffing across many accounts)
    """

    def __init__(
        self,
        max_attempts_per_key: int = 5,
        max_attempts_per_ip: int = 20,
        window_seconds: int = 300,
    ):
        self.max_attempts_per_key = max_attempts_per_key
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds

        self._backend = DistributedRateLimiter(
            prefix="login",
            max_attempts=max_attempts_per_key,
            window_seconds=window_seconds,
        )

    def is_rate_limited_key(self, key: str) -> bool:
        """Check if an IP+email combination is rate-limited (per-account protection)."""
        return self._backend.is_rate_limited(key, threshold=self.max_attempts_per_key)

    def is_rate_limited_ip(self, ip: str) -> bool:
        """Check if a bare IP is rate-limited (global safety net, higher threshold)."""
        return self._backend.is_rate_limited(ip, threshold=self.max_attempts_per_ip)

    def record_failure(self, key: str) -> int:
        """Record a failed login attempt for a key (either rate_key or client_ip)."""
        return self._backend.record_attempt(key, window_seconds=self.window_seconds)

    def record_attempt(self, key: str) -> int:
        """Record a login attempt for a key."""
        return self._backend.record_attempt(key, window_seconds=self.window_seconds)

    def reset(self, key: str):
        """Reset failed login attempts for a key on successful login."""
        self._backend.reset(key)

    def get_remaining_seconds(self, key: str) -> int:
        """Return remaining lockout seconds for key."""
        return self._backend.get_remaining_seconds(key, threshold=None)

    def get_status(self, key: str, threshold: Optional[int] = None) -> dict:
        """Return non-sensitive diagnostic info for a rate-limit key."""
        limit = threshold if threshold is not None else (
            self.max_attempts_per_key if ":" in key else self.max_attempts_per_ip
        )
        return self._backend.get_status(key, threshold=limit)


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
        return self._backend.is_rate_limited(ip, threshold=self.max_attempts_per_ip)

    def record_attempt(self, ip: str) -> int:
        return self._backend.record_attempt(ip, window_seconds=self.window_seconds)

    def reset(self, ip: str):
        self._backend.reset(ip)

    def get_remaining_seconds(self, ip: str) -> int:
        return self._backend.get_remaining_seconds(ip, threshold=self.max_attempts_per_ip)

    def get_status(self, ip: str) -> dict:
        return self._backend.get_status(ip, threshold=self.max_attempts_per_ip)


# Global instances matching ai_backend.py integration points
login_limiter = LoginRateLimiter(
    max_attempts_per_key=5,
    max_attempts_per_ip=20,
    window_seconds=300
)

signup_limiter = SignupRateLimiter(
    max_attempts_per_ip=15,
    window_seconds=300
)
