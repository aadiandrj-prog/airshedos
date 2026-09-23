"""Standalone, offline receiver example. No AirshedOS app imports or network calls."""

import argparse
import hashlib
import hmac
import json
import math
import re
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

MAX_PACKET_BYTES = 2 * 1024 * 1024
DEFAULT_SCHEMA = (
    Path(__file__).resolve().parents[3] / "docs/contracts/pollution_event_v1.schema.json"
)


class ReceiverError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiverError("Duplicate JSON keys are not accepted")
        result[key] = value
    return result


def reject_constant(_):
    raise ReceiverError("Non-finite JSON numbers are not accepted")


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ReceiverError("Non-finite JSON numbers are not accepted")
    return number


formats = FormatChecker()


@formats.checks("date-time", raises=ValueError)
def aware_rfc3339(value):
    if not isinstance(value, str):
        return True  # Schema type validation owns non-string values.
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", value):
        return False
    return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None


def verify_packet(data: bytes, expected_sha256: str, schema: dict) -> dict:
    if not data or len(data) > MAX_PACKET_BYTES:
        raise ReceiverError("Packet is empty or exceeds the example's 2 MiB limit")
    if not re.fullmatch("[a-f0-9]{64}", expected_sha256):
        raise ReceiverError("Provide the expected lowercase SHA-256 from the sender record")
    digest = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(digest, expected_sha256):
        raise ReceiverError("Integrity mismatch: bytes differ from the expected hash")
    try:
        packet = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_number,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReceiverError("Invalid UTF-8 JSON packet") from exc
    if not isinstance(packet, dict) or packet.get("schema_version") != "pollution_event_v1":
        raise ReceiverError("Missing or unsupported schema_version")
    Draft202012Validator.check_schema(schema)
    if not Draft202012Validator(schema, format_checker=formats).is_valid(packet):
        raise ReceiverError("Packet does not satisfy the PollutionEvent v1 JSON Schema")
    # These existing backend cross-field validators are not represented by JSON Schema.
    times = [
        datetime.fromisoformat(packet[k].replace("Z", "+00:00"))
        for k in ("created_at", "updated_at", "handoff_created_at")
    ]
    if (
        packet["origin_jurisdiction"] == packet["destination_jurisdiction"]
        or packet["origin_case_id"] != packet["case_id"]
        or packet["evidence"]["report_id"] != packet["evidence"]["gemini"]["source_report_id"]
        or len(set(times)) != 1
        or packet["review_state"] not in ("UNDER_REVIEW", "ACKNOWLEDGED", "MONITORING")
        or type(packet["event_version"]) is not int
        or type(packet["source_review_revision"]) is not int
    ):
        raise ReceiverError("Inconsistent frozen packet references, review state or versions")
    return {
        "status": "PASS",
        "schema_version": packet["schema_version"],
        "event_id": packet["event_id"],
        "event_version": packet["event_version"],
        "from": packet["origin_jurisdiction"],
        "to": packet["destination_jurisdiction"],
        "possible_event": packet["possible_event_type"],
        "corroboration": packet["corroboration_support"],
        "synthetic": packet["evidence"]["is_synthetic"],
        "simulated": packet["simulated"],
        "forecast_provider": packet["forecast"]["provider"] if packet["forecast"] else None,
        "sha256": digest,
        "notice": "Offline validation only; no receipt, authenticity or authority integration.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument(
        "--sha256", required=True, help="Expected digest from sender, not this file"
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        with args.packet.open("rb") as handle:
            data = handle.read(MAX_PACKET_BYTES + 1)
        result = verify_packet(data, args.sha256, json.loads(args.schema.read_text()))
    except (ReceiverError, OSError, ValueError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, ReceiverError) else "Packet/schema could not be read"
        print(json.dumps({"status": "FAIL", "reason": message}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
