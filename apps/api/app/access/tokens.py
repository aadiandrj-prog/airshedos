import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import jwt


class InvalidIdentity(Exception):
    pass


@dataclass(frozen=True)
class TokenSettings:
    issuer: str
    audience: str
    client_id: str

    def __post_init__(self):
        parsed = urlsplit(self.issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path != "/"
            or parsed.query
            or parsed.fragment
            or self.audience != "urn:airshedos:pilot-api"
            or not self.client_id
        ):
            raise ValueError(
                "Explicit canonical managed issuer, pilot audience and client required"
            )


class JwksKeys:
    """Fixed server-configured URL; bounded body/timeout/cache/unknown-key refresh.

    PyJWT parses JWKs and verifies signatures. Token headers never choose a URL.
    One unknown-key refresh per minute/process; configured rotation TTL is five minutes.
    """

    def __init__(self, settings):
        self.url = settings.issuer + ".well-known/jwks.json"
        self.lock = threading.Lock()
        self.keys, self.loaded_at, self.last_fetch = {}, 0.0, -60.0

    def __call__(self, kid):
        with self.lock:
            now = time.monotonic()
            if kid in self.keys and now - self.loaded_at < 300:
                return self.keys[kid]
            if now - self.last_fetch < 60:
                raise InvalidIdentity("Identity unavailable")
            self.last_fetch = now
            try:
                with httpx.stream("GET", self.url, timeout=5, follow_redirects=False) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 65536:
                            raise InvalidIdentity("Identity unavailable")
                import json

                document = json.loads(data)
                if not 1 <= len(document["keys"]) <= 16:
                    raise InvalidIdentity("Identity unavailable")
                keys = {}
                for item in document["keys"]:
                    if (
                        item.get("kty") == "RSA"
                        and item.get("use", "sig") == "sig"
                        and item.get("alg", "RS256") == "RS256"
                    ):
                        parsed = jwt.PyJWK.from_dict(item, algorithm="RS256")
                        if parsed.key.key_size < 2048 or parsed.key_id in keys:
                            raise InvalidIdentity("Identity unavailable")
                        keys[parsed.key_id] = parsed.key
                self.keys, self.loaded_at = keys, now
            except (httpx.HTTPError, ValueError, KeyError, jwt.PyJWTError) as exc:
                raise InvalidIdentity("Identity unavailable") from exc
            if kid not in self.keys:
                raise InvalidIdentity("Identity unavailable")
            return self.keys[kid]


class AccessTokenVerifier:
    def __init__(self, settings: TokenSettings, keys=None):
        self.settings, self.keys = settings, keys or JwksKeys(settings)

    def verify(self, token):
        if not isinstance(token, str) or len(token) > 16384:
            raise InvalidIdentity("Invalid session")
        try:
            header = jwt.get_unverified_header(token)  # Routing only; never used as identity.
            if (
                header.get("alg") != "RS256"
                or header.get("typ") not in {"at+jwt", "application/at+jwt"}
                or not isinstance(header.get("kid"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", header["kid"])
                or set(header) & {"jku", "x5u", "jwk", "crit"}
            ):
                raise InvalidIdentity("Invalid session")
            claims = jwt.decode(
                token,
                self.keys(header["kid"]),
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.audience,
                leeway=60,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "jti", "client_id"]},
            )
            if (
                claims["client_id"] != self.settings.client_id
                or not all(
                    isinstance(claims[k], str) and 1 <= len(claims[k]) <= 255
                    for k in ("sub", "jti", "client_id")
                )
                or not isinstance(claims.get("scope"), str)
                or "access:airshedos" not in claims["scope"].split()
                or type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or not 0 < claims["exp"] - claims["iat"] <= 600
            ):
                raise InvalidIdentity("Invalid session")
            return claims
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise InvalidIdentity("Invalid session") from exc
