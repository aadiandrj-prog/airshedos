"""Private R2/S3 adapter. No originals, public URLs, ACLs or browser presigned links."""

import re
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.persistence.contracts import PersistenceError
from app.persistence.media import KEY, MAX_UPLOAD_BYTES

PREFIX = "seva-private/derivatives/"


class S3PrivateMediaStore:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    @classmethod
    def from_env(cls, env):
        # This explicit gate records operator approval; it cannot certify bucket policy.
        if env.get("PRIVATE_MEDIA_APPROVED") != "1" or env.get("MEDIA_BACKEND") != "s3":
            return None
        endpoint = env["S3_ENDPOINT_URL"]
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or not re.fullmatch(r"[a-f0-9]{32}\.r2\.cloudflarestorage\.com", parsed.netloc)
        ):
            raise ValueError("Private R2 endpoint required")
        bucket = env["S3_BUCKET"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise ValueError("Private bucket name required")
        if not env.get("S3_ACCESS_KEY_ID") or not env.get("S3_SECRET_ACCESS_KEY"):
            raise ValueError("Explicit private storage credentials required")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=env.get("S3_REGION", "auto"),
            aws_access_key_id=env["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=env["S3_SECRET_ACCESS_KEY"],
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=10,
                max_pool_connections=5,
                retries={"max_attempts": 2, "mode": "standard"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        return cls(client, bucket)

    @staticmethod
    def _key(key):
        if not KEY.fullmatch(key):
            raise ValueError("Invalid private object identifier")
        return PREFIX + key

    def _call(self, operation, **kwargs):
        try:
            return getattr(self.client, operation)(**kwargs)
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                raise FileNotFoundError("Private derivative unavailable") from None
            raise PersistenceError("Private object storage unavailable") from None
        except BotoCoreError:
            raise PersistenceError("Private object storage unavailable") from None

    def put_derivative(self, key, data):
        if not 0 < len(data) <= MAX_UPLOAD_BYTES:
            raise ValueError("Invalid derivative size")
        self._call(
            "put_object",
            Bucket=self.bucket,
            Key=self._key(key),
            Body=data,
            ContentType="image/jpeg",
            CacheControl="private, no-store",
            IfNoneMatch="*",
        )

    def read(self, key):
        response = self._call("get_object", Bucket=self.bucket, Key=self._key(key))
        body = response["Body"]
        try:
            if response["ContentLength"] > MAX_UPLOAD_BYTES:
                raise ValueError("Invalid derivative size")
            data = body.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise ValueError("Invalid derivative size")
            return data
        except BotoCoreError:
            raise PersistenceError("Private object storage unavailable") from None
        finally:
            body.close()

    def delete(self, key):
        self._call("delete_object", Bucket=self.bucket, Key=self._key(key))

    def exists(self, key):
        try:
            self._call("head_object", Bucket=self.bucket, Key=self._key(key))
            return True
        except FileNotFoundError:
            return False

    def inventory(self):
        paginator = self.client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=PREFIX):
                for item in page.get("Contents", []):
                    if not item["Key"].startswith(PREFIX):
                        continue
                    key = item["Key"].removeprefix(PREFIX)
                    if KEY.fullmatch(key):
                        yield key, item["LastModified"].timestamp()
        except (ClientError, BotoCoreError):
            raise PersistenceError("Private object inventory unavailable") from None


class NoMediaStore:
    requires_empty_media = True

    """Explicit text-only cleanup; refuses any remaining private object to delete."""

    def delete(self, _key):
        raise PersistenceError("Private storage required to purge existing media")

    def inventory(self):
        return []
