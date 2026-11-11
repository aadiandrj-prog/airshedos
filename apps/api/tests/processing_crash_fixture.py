"""Local-only subprocess proof. Never included in the production API image."""

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.engine import make_url  # noqa: E402

from app.persistence.database import database  # noqa: E402
from app.persistence.repository import DurableRepository  # noqa: E402
from app.processing.worker import ProcessingWorker  # noqa: E402


async def main():
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if (
        parsed.host != "127.0.0.1"
        or parsed.database != "seva_phase1_test"
        or parsed.username != "seva_test"
    ):
        raise SystemExit("Disposable local fixture database required")
    engine, sessions = database(url)
    try:
        w = ProcessingWorker(DurableRepository(sessions), None, None, None)

        async def collect(*_args, **_kwargs):
            print("COLLECTING", flush=True)
            await asyncio.Event().wait()

        w.collector = SimpleNamespace(collect=collect)
        await w.run_once()
    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
