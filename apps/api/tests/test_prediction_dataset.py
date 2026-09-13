"""No external calls. Numerical expectations and deliberate leakage mutations."""

import json

import httpx
import numpy as np
import pandas as pd
import pytest

from prediction.common import ERA5_BANDS, DatasetError, RawCache, chunks, hourly
from prediction.coverage import coverage_report, longest_gap, select_stations
from prediction.evaluation import baselines, classification, feature_matrix, regression, validate
from prediction.fixtures import synthetic_inputs
from prediction.frame import (
    FrameConfig,
    apply_spike_rule,
    construct,
    fire_features,
    freeze_spike_rule,
    spike_labels,
    split_boundaries,
)
from prediction.openaq import AQ_COLUMNS, OpenAQ, deduplicate, normalize_hours
from prediction.pipeline import build, load_artifacts, write_artifacts
from prediction.weather import ERA5, normalize_era5, wind

SENSOR = {"id": 1, "parameter": {"name": "pm25", "units": "ug/m3"}}
RETRIEVED = "2026-01-01T00:00:00Z"


def raw_hour(**changes):
    row = {
        "parameter": SENSOR["parameter"].copy(),
        "value": 42.5,
        "period": {
            "datetimeFrom": {"utc": "2025-01-01T00:00:00Z"},
            "datetimeTo": {"utc": "2025-01-01T01:00:00Z"},
        },
        "coverage": {"percentCoverage": 100},
    }
    row.update(changes)
    return row


@pytest.fixture(scope="module")
def inputs():
    return synthetic_inputs()


@pytest.fixture(scope="module")
def built(inputs):
    frame, features = construct(*inputs)
    frozen = freeze_spike_rule(frame)
    return apply_spike_rule(frame, frozen), features, frozen


def test_hourly_normalization_provenance():
    item = normalize_hours([raw_hour()], 91, SENSOR, RETRIEVED)[0]
    assert item["value"] == 42.5 and item["unit"] == "µg/m³"
    assert item["timestamp"] == pd.Timestamp("2025-01-01T01:00Z")
    assert item["period_start"] == item["timestamp"] - pd.Timedelta(hours=1)
    assert item["station_id"] == "91" and item["sensor_id"] == 1
    assert item["retrieved_at"] == pd.Timestamp(RETRIEVED)
    assert pd.isna(item["available_at"])


@pytest.mark.parametrize(
    "value,coverage",
    [
        (-1, 100),
        (None, 100),
        (float("nan"), 100),
        (float("inf"), 100),
        (True, 100),
        (3, 74.9),
        (3, None),
        (3, 101),
    ],
)
def test_bad_aq_is_missing_not_interpolated(value, coverage):
    item = normalize_hours(
        [raw_hour(value=value, coverage={"percentCoverage": coverage})], 1, SENSOR, RETRIEVED
    )[0]
    assert item["value"] is None


@pytest.mark.parametrize("unit", ["ppb", "ppm", "µg/m³"])
def test_gas_units_preserved(unit):
    sensor = {"id": 2, "parameter": {"name": "no2", "units": unit}}
    item = normalize_hours([raw_hour(parameter=sensor["parameter"])], 1, sensor, RETRIEVED)[0]
    assert item["unit"] == unit and item["value"] == 42.5


@pytest.mark.parametrize(
    "change",
    [
        {"parameter": {"name": "co", "units": "ug/m3"}},
        {"parameter": {"name": "pm25", "units": "ppb"}},
        {
            "period": {
                "datetimeFrom": {"utc": "2025-01-01T00:00Z"},
                "datetimeTo": {"utc": "2025-01-01T02:00Z"},
            }
        },
        {
            "period": {
                "datetimeFrom": {"utc": "2025-01-01T00:30Z"},
                "datetimeTo": {"utc": "2025-01-01T01:30Z"},
            }
        },
        {"period": {}},
    ],
)
def test_malformed_or_wrong_identity_fails(change):
    with pytest.raises(DatasetError):
        normalize_hours([raw_hour(**change)], 1, SENSOR, RETRIEVED)


def test_duplicate_and_revision_policy():
    frame = pd.DataFrame(normalize_hours([raw_hour(), raw_hour()], 1, SENSOR, RETRIEVED))
    assert len(deduplicate(frame)) == 1
    frame.loc[1, "value"] = 43
    with pytest.raises(DatasetError, match="Conflicting duplicate"):
        deduplicate(frame)


def api_fake(tmp_path, handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAQ(
        "fixture-key-not-secret",
        RawCache(tmp_path),
        client=client,
        sleep=lambda _: None,
        min_interval_seconds=0,
        **kwargs,
    )


def test_pagination_unknown_total_and_cache(tmp_path):
    seen = []

    def handler(request):
        page = int(request.url.params["page"])
        seen.append(page)
        return httpx.Response(
            200,
            json={
                "meta": {"found": ">1000"},
                "results": [{"id": page * 2}, {"id": page * 2 + 1}] if page < 3 else [],
            },
        )

    api = api_fake(tmp_path, handler)
    assert sum(len(rows) for rows, _ in api.pages("locations", limit=2)) == 4
    assert seen == [1, 2, 3]
    list(api.pages("locations", limit=2))
    assert seen == [1, 2, 3] and api.cache.hits == 3
    assert "fixture-key" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


@pytest.mark.parametrize("mode", ["repeat", "cap"])
def test_pagination_refuses_silent_truncation(tmp_path, mode):
    api = api_fake(
        tmp_path,
        lambda r: httpx.Response(
            200, json={"results": [{"id": 1 if mode == "repeat" else int(r.url.params["page"])}]}
        ),
    )
    with pytest.raises(DatasetError, match="repeated|cap"):
        list(api.pages("locations", limit=1, max_pages=2))


def test_retry_rate_limit_auth_and_budget(tmp_path):
    codes = iter([429, 503, 200])
    api = api_fake(
        tmp_path,
        lambda _: httpx.Response(next(codes), headers={"Retry-After": "1"}, json={"results": []}),
    )
    assert api.page("locations", {})["data"] == {"results": []}
    assert api.requests == 3
    api = api_fake(tmp_path / "auth", lambda _: httpx.Response(401, text="private-content"))
    with pytest.raises(DatasetError, match="authentication") as error:
        api.page("locations", {})
    assert "private-content" not in str(error.value)
    api = api_fake(tmp_path / "budget", lambda _: httpx.Response(200), max_requests=0)
    with pytest.raises(DatasetError, match="budget"):
        api.page("locations", {})


def test_missing_configuration_and_cache_tamper(tmp_path):
    api = OpenAQ("", RawCache(tmp_path))
    with pytest.raises(DatasetError, match="not configured"):
        api.page("locations", {})
    api.close()
    cache = RawCache(tmp_path)
    cache.put("source", {"start": RETRIEVED}, [1])
    path = cache.path("source", {"start": RETRIEVED})
    value = json.loads(path.read_text())
    value["data"] = [2]
    path.write_text(json.dumps(value))
    with pytest.raises(DatasetError, match="integrity"):
        cache.get("source", {"start": RETRIEVED})


def met_row(t="2025-01-01T00:00Z", station="1"):
    return {
        "station_id": station,
        "time_ms": pd.Timestamp(t).timestamp() * 1000,
        **dict(zip(ERA5_BANDS, (290, 280, 100000, 0.001, 3, 4), strict=True)),
    }


def test_era5_native_units_wind_and_negative_precip():
    raw = met_row()
    raw["total_precipitation_hourly"] = -0.01
    row = normalize_era5([raw], RETRIEVED).iloc[0]
    assert row.temperature_2m == 290 and row.surface_pressure == 100000
    assert row.wind_speed_mps == 5
    assert row.wind_from_degrees == pytest.approx(216.86989764584402)
    assert pd.isna(row.total_precipitation_hourly) and "negative" in row.quality_notes
    assert pd.isna(row.available_at)
    assert ERA5_BANDS["total_precipitation_hourly"] == "m"


@pytest.mark.parametrize("u,v,direction", [(0, -1, 0), (-1, 0, 90), (0, 1, 180), (1, 0, 270)])
def test_wind_direction_from(u, v, direction):
    assert wind(u, v) == (1, direction)
    assert wind(0, 0) == (0, None)


def test_era5_batches_all_stations_and_cache(tmp_path):
    calls = []

    def query(stations, start, end):
        calls.append((stations, start, end))
        return [met_row(start, s["id"]) for s in stations]

    provider = ERA5(None, RawCache(tmp_path), query=query)
    stations = [
        {"id": "1", "latitude": 28.4, "longitude": 77.1},
        {"id": "2", "latitude": 28.6, "longitude": 77.2},
    ]
    result = provider.extract(stations, "2025-01-01T00:00Z", "2025-01-16T00:00Z")
    assert len(calls) == 3 and len(result) == 6
    provider.extract(stations, "2025-01-01T00:00Z", "2025-01-16T00:00Z")
    assert provider.requests == 3 and provider.cache.hits == 3


@pytest.mark.parametrize(
    "response", [[], [met_row(station="other")], [met_row(), met_row()], [{"station_id": "1"}]]
)
def test_era5_malformed_empty_outside_or_duplicate_fails(tmp_path, response):
    provider = ERA5(None, RawCache(tmp_path), query=lambda *_: response)
    with pytest.raises(DatasetError):
        provider.extract(
            [{"id": "1", "latitude": 28.4, "longitude": 77.1}],
            "2025-01-01T00:00Z",
            "2025-01-02T00:00Z",
        )


def test_numerical_lags_rolls_targets_station_isolation(inputs, built):
    aq, _, stations, _ = inputs
    frame, features, _ = built
    t = pd.Timestamp("2025-02-10T12:00Z")
    for station in stations:
        pm = aq[aq.station_id == station["id"]].set_index("timestamp").value
        row = frame[(frame.station_id == station["id"]) & (frame.timestamp == t)].iloc[0]
        for h in (1, 2, 3, 6, 12, 24):
            assert row[f"pm25_lag_{h}h"] == pm[t - pd.Timedelta(hours=h)]
        past = pm.loc[t - pd.Timedelta(hours=5) : t]
        assert row.pm25_rolling_mean_6h == pytest.approx(past.mean())
        assert row.pm25_rolling_std_6h == pytest.approx(past.std(ddof=0))
        future = pm.loc[t + pd.Timedelta(hours=1) : t + pd.Timedelta(hours=6)]
        assert row.future_max_pm25_6h == max(future)
        assert row.future_mean_pm25_6h == pytest.approx(future.mean())
        history = pm[(pm.index > t - pd.Timedelta(days=30)) & (pm.index <= t)]
        assert row.trailing_30d_p90_pm25 == pytest.approx(history.quantile(0.9))
        assert row.hour_of_day == 17  # 12:00 UTC == 17:30 station-local time
    assert not any(c.startswith("future") for c in features)


def test_future_perturbation_does_not_change_past_features(inputs, built):
    aq, weather, stations, config = inputs
    t = pd.Timestamp("2025-02-10T12:00Z")
    altered = aq.copy()
    altered.loc[altered.timestamp > t, "value"] = 9999
    new, features = construct(altered, weather, stations, config)
    old, _, _ = built
    pd.testing.assert_frame_equal(
        new.loc[new.timestamp <= t, features], old.loc[old.timestamp <= t, features]
    )


def test_missing_future_or_past_hours_never_interpolated(inputs):
    aq, weather, stations, config = inputs
    aq = aq.copy()
    t = pd.Timestamp("2025-02-10T12:00Z")
    aq.loc[aq.timestamp == t + pd.Timedelta(hours=3), "value"] = np.nan
    frame, _ = construct(aq, weather, stations, config)
    rows = frame[frame.timestamp == t]
    assert rows.future_observation_count.eq(5).all()
    assert rows.future_max_pm25_6h.isna().all() and not rows.regression_eligible.any()
    later = frame[frame.timestamp == t + pd.Timedelta(hours=4)]
    assert later.pm25_rolling_mean_6h.isna().all()


def test_minimum_trailing_history_and_zero_not_spike(inputs):
    aq, weather, stations, config = inputs
    sparse = aq[aq.timestamp >= hourly(config.start)].copy()
    frame, _ = construct(sparse, weather, stations, config)
    assert (
        frame.loc[
            frame.timestamp < hourly(config.start) + pd.Timedelta(days=23), "trailing_30d_p90_pm25"
        ]
        .isna()
        .all()
    )
    frame["pm25_t"] = frame["future_max_pm25_6h"] = frame["trailing_30d_p90_pm25"] = 0
    assert spike_labels(frame, 90, 0.25).dropna().eq(0).all()


def test_spike_frozen_on_training_only(built):
    frame, _, frozen = built
    assert frozen["selected"] is not None
    changed = frame.copy()
    changed.loc[changed.split != "train", "future_max_pm25_6h"] = 1e9
    assert freeze_spike_rule(changed) == frozen
    selected = frozen["selected"]
    expected = spike_labels(frame, selected["percentile"], selected["relative_increase"])
    pd.testing.assert_series_equal(frame.spike_next_6h, expected, check_names=False)


def test_aligned_splits_purge_and_calendar_boundaries(built):
    frame, _, _ = built
    boundaries = split_boundaries(FrameConfig("2025-01-01T00:00Z", "2026-01-01T00:00Z"))
    assert boundaries["train_end_exclusive"] == "2025-09-01T00:00:00+00:00"
    assert boundaries["validation_end_exclusive"] == "2025-11-01T00:00:00+00:00"
    assert frame.groupby("timestamp").split.nunique().eq(1).all()
    assert frame.split.eq("purged").sum() == 18 * 3
    for first, second in (("train", "validation"), ("validation", "test")):
        assert (
            frame.loc[frame.split == first, "target_window_end"].max()
            < frame.loc[frame.split == second, "timestamp"].min()
        )


@pytest.mark.parametrize(
    "column",
    [
        "pm25_lag_1h",
        "pm25_rolling_mean_6h",
        "trailing_30d_p90_pm25",
        "future_max_pm25_6h",
        "spike_next_6h",
    ],
)
def test_validator_rejects_corrupted_values(inputs, built, column):
    frame, features, frozen = built
    frame = frame.copy()
    frame.loc[100, column] = 12345
    with pytest.raises(DatasetError, match="reconstructed"):
        validate(frame, *inputs, features, frozen)


def test_leakage_allowlist_and_operational_gate(inputs, built):
    frame, features, frozen = built
    report = validate(frame, *inputs, features, frozen)
    assert report["observation_time_checks_pass"] and not report["operational_availability_pass"]
    with pytest.raises(DatasetError, match="Target/split"):
        validate(frame, *inputs, features + ["future_max_pm25_6h"], frozen)
    with pytest.raises(DatasetError, match="availability"):
        validate(frame, *inputs, features, frozen, require_operational=True)
    with pytest.raises(DatasetError, match="availability"):
        feature_matrix(frame, features)
    assert len(feature_matrix(frame, features, require_operational=False)) == len(frame)


def test_exact_fire_observation_and_availability_window():
    t = pd.Timestamp("2025-02-01T00:00Z")
    events = pd.DataFrame(
        {
            "station_id": ["1"] * 5,
            "observed_at": [t, t + pd.Timedelta(hours=1), t - pd.Timedelta(hours=24), t, t],
            "available_at": [t, t, t, t + pd.Timedelta(hours=1), pd.NaT],
            "distance_km": [30, 0, 0, 0, 0],
        }
    )
    row = fire_features(events, "1", [t]).iloc[0]
    assert row.fire_count_25km_prev_24h == 0
    assert row.fire_count_50km_prev_24h == row.fire_count_100km_prev_24h == 1


def test_coverage_and_station_selection(inputs):
    aq, _, stations, config = inputs
    coverage = coverage_report(aq, config.start, config.end)
    assert len(coverage) == 12
    assert longest_gap(pd.Series([1, None, None, 2, None])) == 2
    locations = [
        {**s, "coordinates": {"latitude": s["latitude"], "longitude": s["longitude"]}}
        for s in stations
    ]
    selected = select_stations(locations, coverage, count=3)
    assert len(selected) == 3 and all("Measured" in s["selection_reason"] for s in selected)
    poor = coverage.copy()
    poor.loc[poor.station_id == stations[0]["id"], "missing_percent"] = 90
    assert len(select_stations(locations, poor, count=3)) == 2


def test_optional_pollutant_missingness_does_not_drop_rows(inputs, built):
    aq, weather, stations, config = inputs
    gas = aq.iloc[[0]].copy()
    gas["pollutant"] = "no2"
    gas["unit"] = "ppb"
    frame, features = construct(pd.concat([aq, gas]), weather.iloc[0:0], stations, config)
    assert "no2_ppb_t" in features and len(frame) == len(built[0])
    assert frame.era5_temperature_2m.isna().all()
    with pytest.raises(DatasetError, match="compatible"):
        construct(aq.assign(unit="ppm"), weather, stations, config)


def test_metrics_exact_and_same_population(built):
    assert regression([1, 3], [2, 1]) == {"n": 2, "mae": 1.5, "rmse": np.sqrt(2.5)}
    metrics = classification([1, 1, 0, 0], [1, 0, 1, 0])
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 0.5
    frame, _, frozen = built
    metrics = baselines(frame, frozen)["splits"]["test"]["pooled"]
    assert metrics["persistence"]["n"] == metrics["recent_mean_6h"]["n"]
    assert metrics["always_negative"]["f1"] == 0


def test_artifact_roundtrip_manifest_and_gate(tmp_path, inputs):
    aq, weather, stations, config = inputs
    manifest = write_artifacts(aq, weather, stations, config, tmp_path, [], synthetic=True)
    assert manifest["synthetic"] is True and not manifest["ready_for_operational_training"]
    assert manifest["rows"] == 90 * 24 * 3
    loaded, frame, aq2, weather2 = load_artifacts(tmp_path)
    assert loaded["config"] == config.to_dict()
    assert validate(
        frame,
        aq2,
        weather2,
        stations,
        config,
        loaded["features"],
        loaded["targets"]["spike_next_6h"],
    )["observation_time_checks_pass"]
    assert (tmp_path / "station_coverage.csv").exists()
    with pytest.raises(DatasetError, match="not known"):
        build(None, None, stations, config, tmp_path)


@pytest.mark.parametrize("value", ["2025-01-01", "2025-01-01T01:30Z", "NaT"])
def test_timestamps_require_aware_exact_hour(value):
    with pytest.raises(DatasetError):
        hourly(value)


def test_chunk_end_exclusive():
    periods = list(chunks("2025-01-01T00:00Z", "2025-03-01T00:00Z"))
    assert len(periods) == 3
    assert periods[0][1] == periods[1][0]


def test_discovery_then_full_builder_with_fake_sources(tmp_path, inputs):
    from prediction.pipeline import discover

    aq, weather, stations, config = inputs
    locations = [
        {
            **station,
            "coordinates": {"latitude": station["latitude"], "longitude": station["longitude"]},
            "isMonitor": True,
            "isMobile": False,
        }
        for station in stations
    ]

    def handler(request):
        path = request.url.path
        if path.endswith("/locations"):
            assert request.url.params["iso"] == "IN"
            result = locations
        else:
            sensor_id = int(path.split("/")[3])
            sensor = stations[sensor_id - 1]["sensors"][0]
            if path.endswith("/hours"):
                start = pd.Timestamp(request.url.params["datetime_from"])
                end = pd.Timestamp(request.url.params["datetime_to"])
                rows = aq[
                    (aq.sensor_id == sensor_id) & (aq.timestamp >= start) & (aq.timestamp < end)
                ]
                result = [
                    {
                        "parameter": sensor["parameter"],
                        "value": row.value if pd.notna(row.value) else None,
                        "period": {
                            "datetimeFrom": {"utc": row.period_start.isoformat()},
                            "datetimeTo": {"utc": row.timestamp.isoformat()},
                        },
                        "coverage": {"percentCoverage": 100},
                    }
                    for row in rows.itertuples()
                ]
            else:
                result = [
                    {
                        **sensor,
                        "datetimeFirst": {"utc": "2024-01-01T00:00:00Z"},
                        "datetimeLast": {"utc": "2026-01-01T00:00:00Z"},
                    }
                ]
        return httpx.Response(200, json={"results": result})

    api = api_fake(tmp_path / "cache", handler)
    selected = discover(api, config.start, config.end, tmp_path / "discovery", count=3)
    assert len(selected) == 3

    def query(selected, start, end):
        rows = weather[
            (weather.timestamp >= pd.Timestamp(start)) & (weather.timestamp < pd.Timestamp(end))
        ]
        return [
            {
                "station_id": row.station_id,
                "time_ms": row.timestamp.timestamp() * 1000,
                **{band: getattr(row, band) for band in ERA5_BANDS},
            }
            for row in rows.itertuples()
        ]

    provider = ERA5(None, api.cache, query=query)
    manifest = build(
        api, provider, selected, config, tmp_path / "output", retrospective=True, synthetic=True
    )
    assert manifest["rows"] == 6480 and provider.requests == 18
    assert manifest["synthetic"] and manifest["sensors"]
    sources = json.loads((tmp_path / "output/source_manifest.json").read_text())["sources"]
    assert {source["source"] for source in sources} == {"openaq", "era5"}
    requests = api.requests
    build(api, provider, selected, config, tmp_path / "repeat", retrospective=True, synthetic=True)
    assert api.requests == requests and provider.requests == 18


def test_location_scope_and_metadata_fails_closed(tmp_path):
    row = {
        "id": 1,
        "isMonitor": True,
        "isMobile": False,
        "sensors": [SENSOR],
        "coordinates": {"latitude": 50, "longitude": 0},
        "timezone": "UTC",
    }
    api = api_fake(tmp_path, lambda _: httpx.Response(200, json={"results": [row]}))
    with pytest.raises(DatasetError, match="outside NCR"):
        api.locations()


def test_geographic_spread_after_coverage_gate(inputs):
    aq, _, stations, config = inputs
    coverage = coverage_report(aq, config.start, config.end)
    locations = [
        {
            **station,
            "coordinates": {"latitude": station["latitude"], "longitude": station["longitude"]},
        }
        for station in stations
    ]
    chosen = select_stations(locations, coverage, count=2)
    assert "Geographic spread" in chosen[1]["selection_reason"]
    assert chosen[0]["id"] != chosen[1]["id"]


def test_artifact_tamper_rejected(tmp_path, inputs):
    aq, weather, stations, config = inputs
    write_artifacts(aq, weather, stations, config, tmp_path, [], synthetic=True)
    path = tmp_path / "prediction_frame.parquet"
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(DatasetError, match="checksum"):
        load_artifacts(tmp_path)


def test_era5_timeout_safe_and_configuration(tmp_path):
    def failed(*_):
        raise TimeoutError("do not disclose provider detail")

    provider = ERA5(None, RawCache(tmp_path), query=failed)
    with pytest.raises(DatasetError, match="cached chunks") as error:
        provider.extract(
            [{"id": "1", "latitude": 28.4, "longitude": 77.1}],
            "2025-01-01T00:00Z",
            "2025-01-02T00:00Z",
        )
    assert "disclose" not in str(error.value)
    with pytest.raises(DatasetError, match="not configured"):
        ERA5(None, RawCache(tmp_path)).remote([], "2025-01-01", "2025-01-02")


def test_synthetic_artifact_cannot_unlock_full_cli(tmp_path, inputs, monkeypatch, capsys):
    from prediction.cli import main

    aq, weather, stations, config = inputs
    output = tmp_path / "gate"
    write_artifacts(aq, weather, stations, config, output, [], synthetic=True)
    station_path = tmp_path / "stations.json"
    station_path.write_text(json.dumps(stations))
    monkeypatch.setattr(
        "sys.argv",
        [
            "build",
            "--stations",
            str(station_path),
            "--gate-directory",
            str(output),
            "--output",
            str(tmp_path / "full"),
            "--retrospective-research",
        ],
    )
    assert main("build") == 2
    assert "real multi-station" in capsys.readouterr().out


def test_spike_exact_threshold_and_insufficient_labels():
    frame = pd.DataFrame(
        {
            "regression_eligible": [True] * 4,
            "trailing_30d_p90_pm25": [100, 100, 100, np.nan],
            "pm25_t": [80] * 4,
            "future_max_pm25_6h": [100, 99.99, 110, 200],
        }
    )
    labels = spike_labels(frame, 90, 0.25)
    assert list(labels.iloc[:3]) == [1, 0, 1] and pd.isna(labels.iloc[3])
    frame["split"] = "train"
    frame["trailing_30d_p85_pm25"] = frame["trailing_30d_p95_pm25"] = 100
    assert freeze_spike_rule(frame)["selected"] is None


def test_empty_sensor_still_gets_zero_coverage_report():
    expected = [{"station_id": "empty", "sensor_id": 1, "pollutant": "pm25", "unit": "µg/m³"}]
    report = coverage_report(
        pd.DataFrame(columns=AQ_COLUMNS), "2025-01-01T00:00Z", "2025-02-01T00:00Z", expected
    )
    whole = report[report.month == "all"].iloc[0]
    assert whole.missing_percent == 100 and whole.valid_target_windows == 0
    assert whole.longest_gap_hours == 744
