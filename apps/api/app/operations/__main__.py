"""Offline operator tools. Never migrate, restore a dump or change a remote host implicitly."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.operations.recovery import RecoveryManager, read_manifest, write_manifest
from app.persistence.database import database
from app.persistence.repository import DurableRepository
from app.resident.storage import NoMediaStore, S3PrivateMediaStore


def main():
    p = argparse.ArgumentParser(description="Offline recovery with explicit target acknowledgement")
    p.add_argument(
        "action", choices=["initialise-empty", "export-manifest", "quarantine", "apply", "release"]
    )
    p.add_argument("--target-database", required=True)
    p.add_argument("--epoch", type=UUID)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--manifest-sha256")
    p.add_argument("--ack-source-writes-frozen", action="store_true")
    p.add_argument("--backup-at", type=datetime.fromisoformat)
    args = p.parse_args()
    engine, sessions = database(os.environ["SEVA_RECOVERY_DATABASE_URL"])
    try:
        with sessions() as session:
            if session.scalar(text("SELECT current_database()")) != args.target_database:
                raise ValueError("Explicit database acknowledgement does not match target")
        store = S3PrivateMediaStore.from_env(os.environ)
        if store is None and os.getenv("PILOT_MEDIA_REQUIRED") == "0":
            store = NoMediaStore()
        if args.action == "apply" and store is None:
            raise ValueError("Approved isolated private storage required")
        manager = RecoveryManager(
            DurableRepository(sessions),
            store,
            database_role=os.environ["SEVA_OPERATOR_DATABASE_ROLE"],
        )
        if args.action == "export-manifest":
            if not args.manifest:
                raise ValueError("Private output path required")
            digest = write_manifest(args.manifest, manager.export())
            print(
                json.dumps(
                    dict(status="exported", schema="seva_erasure_manifest_v1", sha256=digest)
                )
            )
            return
        if args.epoch is None:
            raise ValueError("Fresh out-of-band epoch required")
        if args.action == "initialise-empty":
            manager.initialise_empty(args.epoch)
        elif args.action == "quarantine":
            manager.quarantine(args.epoch)
        elif args.action == "apply":
            if not args.ack_source_writes_frozen:
                raise ValueError("Source cutover writes must be frozen before replay")
            if not args.backup_at or not args.manifest or not args.manifest_sha256:
                raise ValueError("Backup time and reviewed manifest with expected hash required")
            manager.apply(
                args.epoch,
                read_manifest(args.manifest, args.manifest_sha256),
                backup_at=args.backup_at,
                expected_sha256=args.manifest_sha256,
            )
        elif args.action == "release":
            if not args.ack_source_writes_frozen:
                raise ValueError("Source cutover freeze must remain in force")
            manager.release(args.epoch, expected_sha256=args.manifest_sha256)
        print(json.dumps(dict(status=args.action)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Recovery refused or incomplete; keep target private and quarantined"
        ) from None
