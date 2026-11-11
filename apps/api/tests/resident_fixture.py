"""Explicit local-only fixture management. Not shipped in the API image or imported by app/."""

import argparse
import ipaddress
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.access.service import AccessService  # noqa: E402
from app.access.tokens import AccessTokenVerifier, JwksKeys, TokenSettings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.contracts import Principal  # noqa: E402
from app.persistence.database import database  # noqa: E402
from app.persistence.media import LocalPrivateMediaStore, PrivateMediaService  # noqa: E402
from app.persistence.models import (  # noqa: E402
    AuthSession,
    Case,
    Identity,
    Job,
    Membership,
    RecoveryControl,
    Unit,
)
from app.persistence.repository import DurableRepository  # noqa: E402
from app.resident.service import ResidentService  # noqa: E402


class FixtureAccessService(AccessService):
    def authenticate(self, authorization, binding):
        try:
            return super().authenticate(authorization, binding)
        except Exception as error:
            chain = []
            while error is not None:
                chain.append(type(error).__name__)
                error = error.__cause__
            print("Synthetic authentication failure: " + "/".join(chain), flush=True)
            raise


def certificates(root):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AirshedOS synthetic test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")]))
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    for filename, content in (
        ("ca.pem", ca.public_bytes(serialization.Encoding.PEM)),
        ("server.pem", certificate.public_bytes(serialization.Encoding.PEM)),
        (
            "server-key.pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        ),
    ):
        target = root / filename
        target.write_bytes(content)
        target.chmod(0o600)


class FixtureRepository(DurableRepository):
    def _schedule(self, session, report, **kwargs):
        request_id = super()._schedule(session, report, **kwargs)
        if kwargs["kind"] == "PROCESS_REPORT":
            session.flush()
            job = session.scalar(select(Job).where(Job.request_id == request_id))
            # Hold the first synthetic run until the browser explicitly releases it.
            # This is deterministic asynchronous UI testing, not a runtime job option.
            job.next_run_at = self.clock() + timedelta(days=1)
        return request_id


def services():
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if (
        parsed.host != "127.0.0.1"
        or parsed.username != "seva_test"
        or parsed.database != "seva_phase1_test"
    ):
        raise ValueError("Named disposable loopback database required")
    issuer = os.environ["TEST_OIDC_ISSUER"]
    transport = os.environ["TEST_OIDC_TRANSPORT"]
    if issuer != "https://resident-fixture.invalid/" or not transport.startswith(
        "https://127.0.0.1:"
    ):
        raise ValueError("Local synthetic issuer transport required")
    engine, sessions = database(url)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        reviewer = session.scalar(
            select(Identity).where(
                Identity.issuer == issuer, Identity.subject == "fixture-reviewer"
            )
        )
        if reviewer is None:
            reviewer = Identity(issuer=issuer, subject="fixture-reviewer", created_at=now)
            session.add(reviewer)
            session.flush()
            unit = Unit(name="Synthetic local triage", approved_at=now, is_prototype=False)
            session.add(unit)
            session.flush()
            session.add(
                Membership(
                    user_id=reviewer.id,
                    unit_id=unit.id,
                    role="REVIEWER",
                    state="ACTIVE",
                    approved_by=reviewer.id,
                    approved_at=now,
                )
            )
            row = AuthSession(
                user_id=reviewer.id,
                issuer=issuer,
                subject=reviewer.subject,
                sdk_key_hash=uuid4().hex + uuid4().hex,
                binding_hash=uuid4().hex + uuid4().hex,
                created_at=now,
                idle_expires_at=now + timedelta(hours=8),
                absolute_expires_at=now + timedelta(hours=8),
            )
            session.add(row)
            session.flush()
            session_id, unit_id = row.id, unit.id
        else:
            unit_id = session.scalar(
                select(Membership.unit_id).where(Membership.user_id == reviewer.id)
            )
            session_id = session.scalar(
                select(AuthSession.id).where(AuthSession.user_id == reviewer.id)
            )
        # Verified synthetic subjects and operator-approved memberships are seeded only
        # by this guarded local test tool. The app exposes no role-selection login.
        other_unit = session.scalar(select(Unit).where(Unit.name == "Synthetic other review unit"))
        if other_unit is None:
            other_unit = Unit(
                name="Synthetic other review unit", approved_at=now, is_prototype=False
            )
            session.add(other_unit)
            session.flush()
        for key, role, scope in (
            ("TEST_REVIEWER_A", "REVIEWER", unit_id),
            ("TEST_REVIEWER_TWO", "REVIEWER", unit_id),
            ("TEST_ADMIN_A", "UNIT_ADMIN", unit_id),
            ("TEST_REVIEWER_B", "REVIEWER", other_unit.id),
        ):
            subject = os.environ.get(key)
            if not subject:
                continue
            account = session.scalar(
                select(Identity).where(Identity.issuer == issuer, Identity.subject == subject)
            )
            if account is None:
                account = Identity(issuer=issuer, subject=subject, created_at=now)
                session.add(account)
                session.flush()
            membership = session.scalar(
                select(Membership).where(
                    Membership.user_id == account.id, Membership.unit_id == scope
                )
            )
            if membership is None:
                session.add(
                    Membership(
                        user_id=account.id,
                        unit_id=scope,
                        role=role,
                        state="ACTIVE",
                        approved_by=reviewer.id,
                        approved_at=now,
                    )
                )
    repo = FixtureRepository(
        sessions,
        require_session=True,
        triage_unit_id=unit_id,
        provider_retention_reviewed=True,
        release_epoch=UUID(os.environ["SEVA_RECOVERY_EPOCH"]),
    )
    with sessions.begin() as session:
        control = session.get(RecoveryControl, "pilot")
        if control is None:
            control = RecoveryControl(name="pilot", state="QUARANTINED")
            session.add(control)
        # Only this guarded disposable-fixture tool may establish its synthetic epoch.
        control.epoch, control.state = repo.release_epoch, "READY"
    media = PrivateMediaService(
        repo, LocalPrivateMediaStore(Path(os.environ["TEST_PRIVATE_ROOT"]).resolve())
    )
    settings = TokenSettings(issuer, "urn:airshedos:pilot-api", "resident-fixture-client")
    keys = JwksKeys(settings)
    # Test transport only; issuer/signatures still verified.
    keys.url = transport + ".well-known/jwks.json"
    access = FixtureAccessService(
        repo,
        AccessTokenVerifier(settings, keys),
        media,
    )
    return engine, access, Principal(issuer, "fixture-reviewer", session_id=session_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["certificates", "serve", "request-information", "process-jobs", "work"]
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--report-id", type=UUID)
    args = parser.parse_args()
    if args.action == "certificates":
        certificates(args.root)
        return
    engine, access, principal = services()
    try:
        if args.action in {"serve", "process-jobs", "work"}:
            import uvicorn

            from app.citizen.models import AnalysisStatus
            from app.citizen.provider import AnalysisFailure
            from app.citizen.settings import CitizenSettings

            class SyntheticUnavailableAnalyzer:
                settings = CitizenSettings(project="synthetic-fixture-only", timeout_seconds=1)

                async def analyze(self, *_args):
                    raise AnalysisFailure(AnalysisStatus.TIMEOUT)

            api = create_app(
                access=access, citizen_analyzer=SyntheticUnavailableAnalyzer(), mode="pilot"
            )
            if args.action == "work":
                import asyncio

                from app.operations.readiness import pulse
                from app.persistence.retention import RetentionService
                from app.processing.queue import DurableQueue
                from app.processing.worker import ProcessingWorker

                async def run():
                    async with api.router.lifespan_context(api):
                        worker = ProcessingWorker(
                            access.repo,
                            api.state.environment,
                            api.state.citizen_analyzer,
                            api.state.corroboration_settings,
                            store=access.media.store,
                            queue=DurableQueue(access.repo, backoff=(0, 0)),
                        )
                        while True:
                            pulse(access.repo, "processing")
                            RetentionService(access.repo, access.media.store).sweep()
                            await worker.run_once()
                            await asyncio.sleep(0.25)

                asyncio.run(run())
                return
            if args.action == "process-jobs":
                import time

                with access.repo.sessions.begin() as session:
                    for job in session.scalars(
                        select(Job).where(
                            Job.report_id == args.report_id,
                            Job.state.in_(["PENDING", "RETRY_WAIT"]),
                        )
                    ):
                        job.next_run_at = None
                if os.getenv("SEVA_TEST_CONTINUOUS_WORKER") == "1":
                    for _ in range(100):
                        with access.repo.sessions() as session:
                            jobs = list(
                                session.scalars(select(Job).where(Job.report_id == args.report_id))
                            )
                            if jobs and all(
                                j.state not in {"PENDING", "RUNNING", "RETRY_WAIT"} for j in jobs
                            ):
                                return
                        time.sleep(0.1)
                    raise SystemExit(
                        "Separate synthetic worker did not finish within the bounded test"
                    )
                import asyncio

                from fastapi.testclient import TestClient

                from app.processing.queue import DurableQueue
                from app.processing.worker import ProcessingWorker

                async def drain(app):
                    queue = DurableQueue(access.repo, backoff=(0, 0))
                    worker = ProcessingWorker(
                        access.repo,
                        app.state.environment,
                        app.state.citizen_analyzer,
                        app.state.corroboration_settings,
                        store=access.media.store,
                        queue=queue,
                    )
                    for _ in range(3):
                        lease = queue.claim(report_id=args.report_id)
                        if lease:
                            await worker.execute(lease)

                with TestClient(api):
                    asyncio.run(drain(api))
                return

            tls = {}
            if os.getenv("SEVA_TEST_RELEASE") == "1":
                root = Path(os.environ["SSL_CERT_FILE"]).parent
                tls = dict(
                    ssl_certfile=str(root / "server.pem"), ssl_keyfile=str(root / "server-key.pem")
                )
            uvicorn.run(
                api, host="127.0.0.1", port=args.port, access_log=False, log_level="error", **tls
            )
        else:
            with access.repo.sessions() as session:
                case = session.scalar(select(Case).where(Case.report_id == args.report_id))
                case_id, revision = case.id, case.revision
            access.repo.add_internal_note(
                principal,
                case_id,
                expected_revision=revision,
                body="INTERNAL FIXTURE NOTE - DO NOT SHOW",
            )
            ResidentService(access.repo).request_information(
                principal,
                case_id,
                expected_revision=revision + 1,
                prompt="Please tell us whether the activity is still ongoing.",
            )
            print("Synthetic information request published")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
