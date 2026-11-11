"""Run one LOCAL synthetic cleanup pass. Schedule every minute during local intake.

No analysis jobs are executed; hosted storage/maintenance needs a later deployment.
"""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from app.persistence.database import database
from app.persistence.media import LocalPrivateMediaStore
from app.persistence.repository import DurableRepository
from app.persistence.retention import RetentionService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True, type=Path)
    args = parser.parse_args()
    url = os.environ["SEVA_LOCAL_DATABASE_URL"]
    if make_url(url).host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This adapter/command is restricted to local synthetic storage")
    engine, sessions = database(url)
    try:
        result = RetentionService(
            DurableRepository(sessions), LocalPrivateMediaStore(args.private_root)
        ).sweep()
        print(json.dumps(result, sort_keys=True))  # Counts only, no paths/identity/content.
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
