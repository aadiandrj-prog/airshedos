"""Test-only factory injection for SDK -> BFF -> FastAPI -> PostgreSQL proof.

Not imported by app/, no login endpoint, no private signing key. Refuses nonlocal
databases and binds loopback. Requires explicit invocation from the identity tests.
"""

import json
import os
import sys
from pathlib import Path

import jwt
import uvicorn
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.access.service import AccessService  # noqa: E402
from app.access.tokens import AccessTokenVerifier, TokenSettings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.database import database  # noqa: E402
from app.persistence.repository import DurableRepository  # noqa: E402


def main():
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if (
        parsed.host != "127.0.0.1"
        or parsed.database != "seva_phase1_test"
        or parsed.username != "seva_test"
    ):
        raise ValueError("Named local synthetic test database required")
    settings = TokenSettings(
        "https://identity-fixture.invalid/", "urn:airshedos:pilot-api", "synthetic-bff"
    )
    public = jwt.PyJWK.from_dict(json.loads(os.environ["TEST_PUBLIC_JWK"]), algorithm="RS256")
    engine, sessions = database(url)
    try:
        verifier = AccessTokenVerifier(settings, keys=lambda kid: public.key)
        api = create_app(access=AccessService(DurableRepository(sessions), verifier), mode="pilot")
        uvicorn.run(
            api, host="127.0.0.1", port=int(sys.argv[1]), access_log=False, log_level="error"
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
