"""One-shot private hosted-media cleanup; schedule each minute before collection.

No analysis jobs execute. Uses separately approved cleanup-role credentials, not the
restricted BFF login. Application startup never runs this management operation.
"""

import json
import os

from app.persistence.database import database
from app.persistence.repository import DurableRepository
from app.persistence.retention import RetentionService
from app.resident.storage import NoMediaStore, S3PrivateMediaStore


def main():
    store = S3PrivateMediaStore.from_env(os.environ)
    if store is None and os.getenv("PILOT_MEDIA_REQUIRED") == "0":
        store = NoMediaStore()
    if store is None:
        raise SystemExit("Approved private storage configuration required")
    engine, sessions = database(os.environ["SEVA_CLEANUP_DATABASE_URL"])
    try:
        print(
            json.dumps(RetentionService(DurableRepository(sessions), store).sweep(), sort_keys=True)
        )
    except Exception:
        raise SystemExit(
            "Private cleanup failed; inspect safe operational state and retry"
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
