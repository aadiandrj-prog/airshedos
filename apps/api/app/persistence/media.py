import hashlib
import os
import re
import stat
from datetime import timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import or_, select

from app.access.limits import charge
from app.citizen.router import validated_image
from app.persistence.contracts import Gone, NotFound, PersistenceError
from app.persistence.models import Media, Report, ReportSupplement

MAX_UPLOAD_BYTES = 4_000_000
KEY = re.compile(r"[0-9a-f]{32}\Z")


class PrivateMediaStore(Protocol):
    def put_derivative(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def inventory(self) -> list[tuple[str, float]]: ...


class LocalPrivateMediaStore:
    """Local synthetic adapter only. No URLs, original names, symlinks or public mount.

    The root is dedicated, owned by the current user, mode 0700; files are 0600.
    Directory-relative operations and O_NOFOLLOW reject path/symlink substitution.
    A future private object-store adapter must provide equivalent reconciliation.
    """

    def __init__(self, root: Path):
        if not root.is_absolute() or set(root.parts) & {"public", "static", ".next"}:
            raise ValueError("Use an absolute dedicated private local directory")
        if root.is_symlink():
            raise ValueError("Private root cannot be a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.resolve() != root.absolute():
            raise ValueError("Private root ancestors cannot be symlinks")
        info = root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Private root must be owned by this user with mode 0700")
        self.root = root

    def _directory(self, key):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ValueError("Invalid private object identifier")
        return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def put_derivative(self, key, data):
        directory = self._directory(key)
        try:
            fd = os.open(
                key,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.fsync(directory)
            except BaseException:
                os.unlink(key, dir_fd=directory)
                raise
        finally:
            os.close(directory)

    def read(self, key):
        directory = self._directory(key)
        try:
            fd = os.open(key, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_UPLOAD_BYTES:
                    raise ValueError("Invalid private derivative")
                return source.read(MAX_UPLOAD_BYTES + 1)
        finally:
            os.close(directory)

    def delete(self, key):
        directory = self._directory(key)
        try:
            try:
                os.unlink(key, dir_fd=directory)
                os.fsync(directory)
            except FileNotFoundError:
                pass
        finally:
            os.close(directory)

    def exists(self, key):
        directory = self._directory(key)
        try:
            try:
                return stat.S_ISREG(os.stat(key, dir_fd=directory, follow_symlinks=False).st_mode)
            except FileNotFoundError:
                return False
        finally:
            os.close(directory)

    def inventory(self):
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return [
                (key, os.stat(key, dir_fd=directory, follow_symlinks=False).st_mtime)
                for key in os.listdir(directory)
                if KEY.fullmatch(key)
            ]
        finally:
            os.close(directory)


class PrivateMediaService:
    def __init__(self, repository, store: PrivateMediaStore):
        self.repository, self.store = repository, store

    def stage(self, principal, data: bytes, mime_type: str):
        repo, now = self.repository, self.repository.clock()
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Pilot image exceeds 4,000,000 bytes")
        clean, clean_mime = validated_image(data, mime_type)
        if len(clean) > MAX_UPLOAD_BYTES:
            raise ValueError("Clean derivative exceeds 4,000,000 bytes")
        key = uuid4().hex
        with repo.sessions.begin() as session:
            user = repo.identity(session, principal, lock=True)
            charge(
                session,
                scope=user.id,
                rule="MEDIA_STAGE",
                period="hour",
                maximum=repo.limits.uploads_per_hour,
            )
            media = Media(
                owner_id=user.id,
                object_key=key,
                mime_type=clean_mime,
                size_bytes=len(clean),
                sha256=hashlib.sha256(clean).hexdigest(),
                state="WRITING",
                created_at=now,
                expires_at=now + timedelta(seconds=repo.retention.staging_seconds),
            )
            session.add(media)
            session.flush()
            media_id = media.id
        # Intent is durable before any bytes exist. Original upload is never written.
        try:
            self.store.put_derivative(key, clean)
            with repo.sessions.begin() as session:
                repo.identity(session, principal, lock=True)
                media = session.scalar(select(Media).where(Media.id == media_id).with_for_update())
                if media.state != "WRITING" or media.expires_at <= repo.clock():
                    raise Gone("Media staging expired")
                media.state = "READY"
        except Exception as exc:
            # If either operation fails, read paths deny WRITING/DELETING immediately.
            # If compensation itself fails, committed intent + expiry remain for maintenance.
            try:
                with repo.sessions.begin() as session:
                    media = session.get(Media, media_id, with_for_update=True)
                    media.state = "DELETING"
            except Exception:
                pass
            try:
                self.store.delete(key)
            except Exception:
                pass
            raise PersistenceError(
                "Private image staging failed; retry or submit text only"
            ) from exc
        return media_id

    def read(self, principal, media_id, *, case_id=None):
        repo = self.repository
        with repo.sessions.begin() as session:
            user = repo.identity(session, principal, lock=True)
            # Hold row locks through bounded object read so purge cannot unlink mid-read.
            if case_id is not None:
                _, case, report = repo._case(session, principal, case_id, lock=True)
                query = select(Media).where(
                    or_(
                        Media.report_id == report.id,
                        Media.supplement_id.in_(
                            select(ReportSupplement.id).where(
                                ReportSupplement.report_id == report.id
                            )
                        ),
                    )
                )
            else:
                query = select(Media).where(Media.owner_id == user.id)
            media = session.scalar(
                query.where(
                    Media.id == media_id,
                    Media.state.in_(["READY", "ATTACHED"]),
                    Media.expires_at > repo.clock(),
                ).with_for_update()
            )
            if media is None or media.expires_at <= repo.clock():
                raise NotFound("Private media not found")
            parent_id = media.report_id
            if media.supplement_id:
                parent_id = session.get(ReportSupplement, media.supplement_id).report_id
            if parent_id:
                report = session.get(Report, parent_id)
                if (
                    report.deletion_state != "ACTIVE"
                    or report.content_expires_at <= repo.clock()
                    or report.withdrawn_at
                ):
                    raise NotFound("Private media not found")
            try:
                content = self.store.read(media.object_key)
            except (OSError, ValueError) as exc:
                raise NotFound("Private media not available") from exc
            if (
                len(content) != media.size_bytes
                or hashlib.sha256(content).hexdigest() != media.sha256
            ):
                raise PersistenceError("Private media integrity check failed")
            return content
