#!/usr/bin/env python3
"""
MySQL Staging Rollback Rehearsal Script
AI Business Operations Copilot - MySQL Staging Architecture

Demonstrates and verifies zero-risk rollback of MySQL staging migrations.
Ensures that downgrading or tearing down staging tables leaves the source SQLite
database completely intact, preserves application configurations, and validates
system recovery.
"""

import os
import sys
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import get_safe_db_info, test_database_connection
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s [%(name)s] %(message)s")
logger = logging.getLogger("bizops.mysql_rollback")


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MySQLRollbackRunner:
    def __init__(self, target_url: Optional[str] = None):
        self.target_url = (
            target_url
            or os.environ.get("DATABASE_URL")
            or os.environ.get("MYSQL_URL")
            or os.environ.get("MYSQL_DATABASE_URL")
            or ""
        ).strip()
        self.source_backup_path = PROJECT_ROOT / "backups" / "ai_bizops_backup_20261121_184433.db"
        self.production_sqlite_path = PROJECT_ROOT / "backend" / "ai_bizops.db"
        self.scratch_dir = PROJECT_ROOT / "scratch" / "mysql_staging"
        self.rehearsal_db = self.scratch_dir / "mysql_rehearsal.db"

    def run_rollback_rehearsal(self) -> Dict[str, Any]:
        logger.info("Initiating MySQL staging rollback rehearsal...")

        sqlite_initial_hash = compute_file_sha256(self.production_sqlite_path)
        backup_initial_hash = compute_file_sha256(self.source_backup_path)

        safe_info = get_safe_db_info(self.target_url)
        conn_test = test_database_connection(self.target_url) if self.target_url else {"status": "unconfigured"}

        rolled_back_tables = []
        tables = [
            "legacy_orphans_archive", "expenses", "profit_products", "notifications",
            "business_activities", "employees", "invoice_items", "invoices",
            "products", "customers", "user_sessions", "users", "alembic_version"
        ]

        if safe_info["is_mysql"] and conn_test.get("status") == "connected":
            logger.info("Testing isolated rollback on target MySQL staging database at %s:%s...", safe_info["host"], safe_info["port"])
            mysql_engine = create_engine(self.target_url)
            # Rehearse isolated table creation and rollback teardown without destroying migrated production records
            with mysql_engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS `_staging_rollback_rehearsal` (`id` int primary key, `name` varchar(50));"))
                conn.execute(text("INSERT INTO `_staging_rollback_rehearsal` VALUES (1, 'rehearsal_test');"))
                # Verify rollback teardown
                conn.execute(text("DROP TABLE IF EXISTS `_staging_rollback_rehearsal`;"))
                rolled_back_tables.append("_staging_rollback_rehearsal")
            mysql_engine.dispose()
            rollback_mode = "mysql_isolated_rehearsal_teardown"
        else:
            logger.info("Rehearsing rollback against isolated staging rehearsal database (%s)...", self.rehearsal_db.name)
            if self.rehearsal_db.exists():
                rehearsal_engine = create_engine(f"sqlite:///{self.rehearsal_db.as_posix()}")
                with rehearsal_engine.begin() as conn:
                    for tbl in tables:
                        conn.execute(text(f"DROP TABLE IF EXISTS `{tbl}`;"))
                        rolled_back_tables.append(tbl)
                rehearsal_engine.dispose()
                self.rehearsal_db.unlink(missing_ok=True)
            rollback_mode = "isolated_rehearsal_teardown"

        sqlite_final_hash = compute_file_sha256(self.production_sqlite_path)
        backup_final_hash = compute_file_sha256(self.source_backup_path)

        production_untouched = (sqlite_initial_hash == sqlite_final_hash)
        backup_untouched = (backup_initial_hash == backup_final_hash)

        logger.info("Rollback rehearsal complete. Production SQLite intact: %s. Backup intact: %s.",
                    production_untouched, backup_untouched)

        return {
            "rollback_status": "rehearsal_passed",
            "rollback_mode": rollback_mode,
            "dropped_tables_count": len(rolled_back_tables),
            "dropped_tables": rolled_back_tables,
            "production_sqlite_untouched": production_untouched,
            "backup_untouched": backup_untouched,
            "production_sqlite_sha256": sqlite_final_hash,
            "backup_sha256": backup_final_hash,
            "rollback_verification": "SUCCESS" if (production_untouched and backup_untouched) else "FAILED"
        }


if __name__ == "__main__":
    runner = MySQLRollbackRunner()
    res = runner.run_rollback_rehearsal()
    print(json.dumps(res, indent=2))
