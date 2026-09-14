from dataclasses import replace

import pandas as pd
import pytest

from prediction.availability import OPERATIONAL_V1, availability_manifest
from prediction.common import DatasetError
from prediction.evaluation import feature_matrix, validate
from prediction.fixtures import synthetic_inputs
from prediction.frame import apply_spike_rule, construct, freeze_spike_rule
from prediction.openaq import normalize_hours
from prediction.publication_probe import update_ledger


@pytest.fixture(scope="module")
def inputs():
    return synthetic_inputs()


@pytest.mark.parametrize("buffer", [1, 2, 72])
def test_buffer_preserves_forecast_origin_and_future_targets(inputs, buffer):
    aq, weather, stations, config = inputs
    config = replace(config, profile=OPERATIONAL_V1, aq_availability_buffer_hours=buffer)
    frame, features = construct(aq, weather, stations, config)
    t = pd.Timestamp("2025-02-10T12:00:00Z")
    row = frame[(frame.station_id == stations[0]["id"]) & (frame.timestamp == t)].iloc[0]
    pm = aq[aq.station_id == stations[0]["id"]].set_index("timestamp").value
    cutoff = t - pd.Timedelta(hours=buffer)
    assert row.pm25_latest_available == pm[cutoff]
    assert row.pm25_rolling_mean_6h == pytest.approx(
        pm.loc[cutoff - pd.Timedelta(hours=5) : cutoff].mean()
    )
    assert (
        row.future_max_pm25_6h
        == pm.loc[t + pd.Timedelta(hours=1) : t + pd.Timedelta(hours=6)].max()
    )
    assert row.aq_feature_cutoff == cutoff
    assert row.target_window_start == t + pd.Timedelta(hours=1)
    assert row.target_window_end == t + pd.Timedelta(hours=6)
    assert not any(name.startswith("era5_") for name in features)
    assert "pm25_t" not in features
    changed = aq.copy()
    changed.loc[changed.timestamp > cutoff, "value"] = 9999
    altered, _ = construct(changed, weather, stations, config)
    pd.testing.assert_frame_equal(
        frame.loc[frame.timestamp == t, features], altered.loc[altered.timestamp == t, features]
    )


def test_operational_manifest_and_explicit_export_acknowledgment(inputs):
    aq, weather, stations, config = inputs
    config = replace(config, profile=OPERATIONAL_V1)
    frame, features = construct(aq, weather, stations, config)
    frozen = freeze_spike_rule(frame)
    frame = apply_spike_rule(frame, frozen)
    manifest = availability_manifest(features, config)
    report = validate(
        frame,
        aq,
        weather,
        stations,
        config,
        features,
        frozen,
        require_operational=True,
        feature_availability=manifest,
    )
    assert report["operational_availability_pass"]
    assert not report["availability_assumption_verified_prospectively"]
    with pytest.raises(DatasetError, match="acknowledgment"):
        feature_matrix(frame, features, feature_availability=manifest)
    assert len(
        feature_matrix(
            frame, features, feature_availability=manifest, accept_conditional_availability=True
        )
    ) == len(frame)
    manifest["features"][0]["deployment_safe"] = False
    with pytest.raises(DatasetError, match="disagree"):
        validate(
            frame, aq, weather, stations, config, features, frozen, feature_availability=manifest
        )


@pytest.mark.parametrize(
    "feature", ["era5_temperature_2m", "pm25_t", "pm25_lag_1h", "future_max_pm25_6h"]
)
def test_operational_profile_rejects_unsafe_candidate_names(inputs, feature):
    config = replace(inputs[3], profile=OPERATIONAL_V1, aq_availability_buffer_hours=2)
    with pytest.raises(DatasetError, match="Unsafe"):
        availability_manifest([feature], config)


def test_research_export_cannot_be_silently_deployed(inputs):
    frame, features = construct(*inputs)
    manifest = availability_manifest(features, inputs[3])
    assert manifest["deployment_label"] == "NOT DEPLOYMENT-SAFE AS CURRENTLY SOURCED"
    assert any(not f["deployment_safe"] for f in manifest["features"])
    with pytest.raises(DatasetError, match="not deployment-safe"):
        feature_matrix(
            frame, features, feature_availability=manifest, accept_conditional_availability=True
        )


def test_half_hour_source_phase_preserved_and_era5_joins_backwards(inputs):
    aq, weather, stations, config = inputs
    aq = aq.copy()
    aq["timestamp"] += pd.Timedelta(minutes=30)
    aq["period_start"] += pd.Timedelta(minutes=30)
    stations = [{**s, "hour_offset_minutes": 30} for s in stations]
    weather = weather.copy()
    weather["temperature_2m"] = range(len(weather))
    frame, _ = construct(aq, weather, stations, config)
    assert frame.timestamp.dt.minute.eq(30).all()
    row = frame[
        (frame.station_id == stations[0]["id"])
        & (frame.timestamp == pd.Timestamp("2025-02-10T12:30Z"))
    ].iloc[0]
    met = weather[
        (weather.station_id == stations[0]["id"])
        & (weather.timestamp == pd.Timestamp("2025-02-10T12:00Z"))
    ].iloc[0]
    assert row.era5_temperature_2m == met.temperature_2m
    assert row.target_window_start == pd.Timestamp("2025-02-10T13:30Z")


def test_known_revision_and_late_publication_excluded_from_inputs(inputs):
    aq, weather, stations, config = inputs
    config = replace(config, profile=OPERATIONAL_V1, aq_availability_buffer_hours=2)
    aq = aq.copy()
    target_hour = pd.Timestamp("2025-02-10T10:00Z")
    aq.loc[(aq.station_id == stations[0]["id"]) & (aq.timestamp == target_hour), "quality"] = (
        "revision_detected"
    )
    aq["available_at"] = pd.to_datetime(aq.available_at, utc=True)
    aq.loc[(aq.station_id == stations[1]["id"]) & (aq.timestamp == target_hour), "available_at"] = (
        target_hour + pd.Timedelta(hours=3)
    )
    frame, _ = construct(aq, weather, stations, config)
    rows = frame[
        (frame.timestamp == target_hour + pd.Timedelta(hours=2))
        & frame.station_id.isin([s["id"] for s in stations[:2]])
    ]
    assert rows.pm25_latest_available.isna().all()
    assert rows.future_max_pm25_6h.notna().all()


def sample(hour, value):
    return {
        "sensor_id": 123,
        "query_start": "2025-01-01T00:00Z",
        "rows": [
            {
                "timestamp": hour,
                "value": value,
                "unit": "µg/m³",
                "quality": "usable",
                "coverage_percent": 100,
            }
        ],
    }


def test_prospective_probe_is_censored_and_preserves_first_value_on_revision():
    first = update_ledger({}, [sample("2025-01-01T01:30Z", 10)], "2025-01-01T03:00Z")
    item = next(iter(first["hours"].values()))
    assert item["left_censored_first_sighting"] and item["first_observed_lag_hours"] == 1.5
    second = update_ledger(first, [sample("2025-01-01T01:30Z", 12)], "2025-01-01T04:00Z")
    item = next(iter(second["hours"].values()))
    assert item["first_value"] == 10 and item["revision_detected"]
    assert item["first_observed_at"] == "2025-01-01T03:00:00+00:00"
    third = update_ledger(second, [sample("2025-01-01T04:30Z", 15)], "2025-01-01T05:00Z")
    newest = third["hours"]["123/2025-01-01T04:30:00+00:00"]
    assert not newest["left_censored_first_sighting"]
    assert newest["publication_lag_lower_bound_hours"] == 0
    assert newest["first_observed_lag_hours"] == 0.5


def test_actual_ncr_hourly_shape_preserves_interval_and_flags():
    sensor = {"id": 123, "parameter": {"name": "pm25", "units": "µg/m³"}}
    raw = {
        "parameter": sensor["parameter"],
        "value": 42.8,
        "flagInfo": {"hasFlags": False},
        "coverage": {"percentCoverage": 100},
        "period": {
            "datetimeFrom": {"utc": "2026-09-09T23:30Z"},
            "datetimeTo": {"utc": "2026-09-10T00:30Z"},
        },
    }
    value = normalize_hours([raw], 1, sensor, "2026-09-14T07:00Z")[0]
    assert value["timestamp"] == pd.Timestamp("2026-09-10T00:30Z")
    assert value["value"] == 42.8
    raw["flagInfo"]["hasFlags"] = True
    assert normalize_hours([raw], 1, sensor, "2026-09-14T07:00Z")[0]["value"] is None


def test_probe_does_not_mutate_previous_snapshot_and_censors_unqueried_history():
    initial = sample("2025-01-03T01:30Z", 10)
    initial["query_start"] = "2025-01-03T00:00Z"
    first = update_ledger({}, [initial], "2025-01-03T03:00Z")
    second = update_ledger(first, [sample("2025-01-03T01:30Z", 12)], "2025-01-03T04:00Z")
    assert not next(iter(first["hours"].values()))["revision_detected"]
    assert next(iter(second["hours"].values()))["revision_detected"]
    older = update_ledger(first, [sample("2025-01-02T01:30Z", 15)], "2025-01-03T05:00Z")
    item = older["hours"]["123/2025-01-02T01:30:00+00:00"]
    assert item["left_censored_first_sighting"]
    assert item["publication_lag_lower_bound_hours"] is None
    with pytest.raises(ValueError, match="advance"):
        update_ledger(first, [initial], "2025-01-03T03:00Z")


def test_daily_quality_gap_is_not_filled_to_create_24h_features(inputs):
    aq, weather, stations, config = inputs
    aq = aq.copy()
    aq.loc[aq.timestamp.dt.hour.eq(19), "value"] = float("nan")
    research, research_features = construct(aq, weather, stations, config)
    assert research.pm25_rolling_mean_24h.isna().all()
    assert "pm25_rolling_mean_24h" in research_features
    operational, features = construct(
        aq, weather, stations, replace(config, profile=OPERATIONAL_V1)
    )
    assert "pm25_rolling_mean_24h" not in features
    assert "pm25_rolling_std_24h" not in features
    assert operational.pm25_latest_available.isna().any()
    assert operational.operational_eligible.any()


def test_empty_weather_values_cannot_pass_extraction(tmp_path):
    from prediction.common import RawCache
    from prediction.weather import ERA5

    provider = ERA5(
        None,
        RawCache(tmp_path),
        query=lambda *_: [
            {
                "station_id": "1",
                "time_ms": int(pd.Timestamp("2025-01-01T00:00Z").timestamp() * 1000),
            }
        ],
    )
    with pytest.raises(DatasetError, match="no usable band values"):
        provider.extract(
            [{"id": "1", "latitude": 28.55, "longitude": 77.22}],
            "2025-01-01T00:00Z",
            "2025-01-02T00:00Z",
        )


@pytest.mark.parametrize("failure", [None, "synthetic", "weather", "features"])
def test_full_extraction_gate_checks_actual_values_and_operational_rows(inputs, tmp_path, failure):
    from prediction.pipeline import verify_real_feasibility, write_artifacts

    aq, weather, stations, config = inputs
    config = replace(
        config, end="2025-01-29T00:00:00Z", profile=OPERATIONAL_V1, aq_availability_buffer_hours=2
    )
    aq, weather = aq.copy(), weather.copy()
    if failure == "weather":
        weather["temperature_2m"] = float("nan")
    if failure == "features":
        # Some target windows remain, but no complete 12h PM rolling feature exists.
        aq.loc[aq.timestamp.dt.hour.isin([0, 10, 20]), "value"] = float("nan")
    write_artifacts(
        aq, weather, stations[:2], config, tmp_path, [], synthetic=failure == "synthetic"
    )
    if failure:
        with pytest.raises(
            DatasetError,
            match={
                "synthetic": "real multi-station",
                "weather": "complete ERA5",
                "features": "complete operational",
            }[failure],
        ):
            verify_real_feasibility(tmp_path)
    else:
        assert verify_real_feasibility(tmp_path)["status"] == "pass"


def test_export_rejects_future_input_and_mismatched_buffer(inputs):
    config = replace(inputs[3], profile=OPERATIONAL_V1)
    frame, features = construct(*inputs[:3], config)
    manifest = availability_manifest(features, config)
    frame.loc[0, "feature_observation_end"] = frame.loc[0, "timestamp"]
    with pytest.raises(DatasetError, match="cutoff"):
        feature_matrix(
            frame, features, feature_availability=manifest, accept_conditional_availability=True
        )
    frame.loc[:, "aq_availability_buffer_hours"] = 2
    with pytest.raises(DatasetError, match="buffer differs"):
        feature_matrix(
            frame, features, feature_availability=manifest, accept_conditional_availability=True
        )


def test_quota_headers_preserved_without_credentials_and_low_quota_stops(tmp_path):
    import httpx

    from prediction.common import RawCache
    from prediction.openaq import OpenAQ

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"results": []},
                headers={
                    "x-ratelimit-remaining": "5",
                    "x-ratelimit-limit": "60",
                    "authorization": "private-response-value",
                },
            )
        )
    )
    api = OpenAQ("fixture-key", RawCache(tmp_path), client=client)
    api.page("locations", {})
    assert api.response_metadata[0]["headers"] == {
        "x-ratelimit-remaining": "5",
        "x-ratelimit-limit": "60",
    }
    # Frozen cache remains usable even when a new request is prohibited.
    api.page("locations", {})
    with pytest.raises(DatasetError, match="quota is low"):
        api.page("locations", {"page": 2})
    assert api.requests == 1
    api.close()


def test_probe_does_not_claim_absence_for_unqueried_end_of_previous_poll():
    initial = sample("2025-01-01T01:30Z", 10)
    initial["query_end"] = "2025-01-01T02:00Z"
    first = update_ledger({}, [initial], "2025-01-01T03:00Z")
    next_poll = update_ledger(first, [sample("2025-01-01T02:30Z", 12)], "2025-01-01T04:00Z")
    item = next_poll["hours"]["123/2025-01-01T02:30:00+00:00"]
    assert item["left_censored_first_sighting"]
    assert item["publication_lag_lower_bound_hours"] is None


def test_common_window_selection_uses_completed_measured_audit(inputs, tmp_path, monkeypatch):
    import json

    from prediction.common import write_json
    from scripts.select_prediction_window import main

    aq, _, stations, config = inputs
    audit = tmp_path / "audit"
    (audit / "normalized").mkdir(parents=True)
    inventory, locations = [], []
    for station in stations:
        sensor = station["pm25_sensor_id"]
        part = aq[(aq.station_id == station["id"]) & (aq.timestamp >= pd.Timestamp(config.start))]
        part.to_parquet(audit / "normalized" / f"sensor_{sensor}.parquet", index=False)
        location = {
            **station,
            "coordinates": {"latitude": station["latitude"], "longitude": station["longitude"]},
        }
        locations.append(location)
        inventory.append(
            {
                "assessment": "hourly_measured",
                "station_id": station["id"],
                "name": station["name"],
                "coordinates": location["coordinates"],
                "timezone": station["timezone"],
                "provider": None,
                "instruments": [],
                "sensor": {"id": sensor},
            }
        )
    write_json(audit / "candidate_inventory.json", inventory)
    write_json(audit / "locations.json", locations)
    write_json(
        audit / "audit_summary.json",
        {"start": config.start, "end": config.end, "measured_sensors": len(stations)},
    )
    output = tmp_path / "selected"
    monkeypatch.setattr("sys.argv", ["select", "--audit", str(audit), "--output", str(output)])
    assert main() == 0
    chosen = json.loads((output / "selected_stations.json").read_text())
    assert len(chosen) == 3
    assert {s["id"] for s in chosen} == {s["id"] for s in stations}
    window = json.loads((output / "window_selection.json").read_text())
    assert window["days"] == 90 and window["requests"] == 0


def test_empty_month_chunks_keep_typed_hours_without_concat_warning(tmp_path):
    import warnings

    import httpx

    from prediction.common import RawCache
    from prediction.openaq import OpenAQ

    sensor = {"id": 1, "parameter": {"name": "pm25", "units": "µg/m³"}}
    row = {
        "parameter": sensor["parameter"],
        "value": 10.0,
        "coverage": {"percentCoverage": 100},
        "period": {
            "datetimeFrom": {"utc": "2025-02-01T00:30Z"},
            "datetimeTo": {"utc": "2025-02-01T01:30Z"},
        },
    }

    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": []
                if request.url.params["datetime_from"].startswith("2025-01-01")
                else [row]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    api = OpenAQ("fixture-key", RawCache(tmp_path), client=client, sleep=lambda _: None)
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = api.hours("1", sensor, "2025-01-01T00:00Z", "2025-02-03T00:00Z")
    assert len(result) == 1 and result.value.iloc[0] == 10
    assert result.timestamp.iloc[0] == pd.Timestamp("2025-02-01T01:30Z")
    assert not [w for w in recorded if issubclass(w.category, FutureWarning)]
    api.close()
