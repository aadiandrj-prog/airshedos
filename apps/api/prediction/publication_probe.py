"""One bounded prospective poll. First sighting is an upper bound, not publication time."""

from copy import deepcopy

from prediction.common import digest, utc


def update_ledger(previous, samples, polled_at):
    now = utc(polled_at)
    result = {
        "version": "openaq_first_seen_v1",
        "hours": deepcopy(previous.get("hours", {})),
        "last_successful_poll": dict(previous.get("last_successful_poll", {})),
        "last_query_start": dict(previous.get("last_query_start", {})),
        "last_query_end": dict(previous.get("last_query_end", {})),
    }
    reports = []
    for sample in samples:
        sensor = str(sample["sensor_id"])
        last_poll = result["last_successful_poll"].get(sensor)
        previous_time = utc(last_poll) if last_poll else None
        if previous_time is not None and now <= previous_time:
            raise ValueError("Prospective polls must advance in time")
        latest = None
        revisions = 0
        for row in sample["rows"]:
            end = utc(row["timestamp"])
            if end > now:
                raise ValueError("Future measurement in prospective poll")
            latest = max(latest, end) if latest is not None else end
            key = f"{sensor}/{end.isoformat()}"
            signature = digest(
                {k: row.get(k) for k in ("value", "unit", "coverage_percent", "quality")}
            )
            item = result["hours"].get(key)
            if item is None:
                prior_start = result["last_query_start"].get(sensor)
                prior_end = result["last_query_end"].get(sensor)
                left_censored = previous_time is None or (
                    end < previous_time
                    and (
                        prior_start is None
                        or end < utc(prior_start)
                        or prior_end is None
                        or end > utc(prior_end)
                    )
                )
                item = {
                    "sensor_id": int(sensor),
                    "measurement_hour": end.isoformat(),
                    "first_observed_at": now.isoformat(),
                    "first_value": row.get("value"),
                    "unit": row.get("unit"),
                    "first_value_hash": signature,
                    "first_observed_lag_hours": (now - end).total_seconds() / 3600,
                    "publication_lag_lower_bound_hours": None
                    if left_censored
                    else max(0, (previous_time - end).total_seconds() / 3600),
                    "left_censored_first_sighting": left_censored,
                    "interpretation": "first-seen upper bound; not exact provider publication time",
                    "revision_detected": False,
                }
            elif signature != item["latest_value_hash"]:
                item["revision_detected"] = True
                revisions += 1
            item["last_observed_at"] = now.isoformat()
            item["latest_value_hash"] = signature
            result["hours"][key] = item
        result["last_successful_poll"][sensor] = now.isoformat()
        result["last_query_start"][sensor] = utc(sample["query_start"]).isoformat()
        result["last_query_end"][sensor] = utc(sample.get("query_end", now)).isoformat()
        reports.append(
            {
                "sensor_id": int(sensor),
                "rows": len(sample["rows"]),
                "latest_measurement_hour": latest.isoformat() if latest is not None else None,
                "latest_measurement_age_hours": (now - latest).total_seconds() / 3600
                if latest is not None
                else None,
                "revisions_detected_this_poll": revisions,
            }
        )
    result["last_report"] = {"polled_at": now.isoformat(), "sensors": reports}
    return result
