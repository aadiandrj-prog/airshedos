import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.environment.forecast_models import AirQualityForecastContext

spec = importlib.util.spec_from_file_location(
    "snapshot", Path(__file__).parents[1] / "scripts/forecast_snapshot.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_prospective_snapshot_and_exact_observation_matching():
    context = AirQualityForecastContext.model_validate(
        json.loads((Path(__file__).parents[2] / "web/e2e/fixtures/forecast.test.json").read_text())
    )
    saved = module.snapshot(context)
    assert saved["issued_at"] is None
    assert saved["hourly"][0]["pm25"]["unit"] == "MICROGRAMS_PER_CUBIC_METER"
    assert saved["hourly"][0]["cpcb_aqi"] == next(
        i.value for i in context.hourly_forecasts[0].indexes if i.code == "ind_cpcb"
    )
    saved["recorded_at"] = (context.retrieved_at + timedelta(seconds=1)).isoformat()
    observation = context.current_air_quality.model_copy(deep=True)
    observation.observed_at = context.hourly_forecasts[0].forecast_at
    matched = module.match_observation(saved, observation)
    assert matched["provider"] == "google_air_quality"
    assert matched["provenance"] == observation.provenance.model_dump(mode="json")
    observation.observed_at += timedelta(minutes=1)
    with pytest.raises(ValueError, match="exact"):
        module.match_observation(saved, observation)
    observation.observed_at = context.retrieved_at
    with pytest.raises(ValueError, match="follow"):
        module.match_observation(saved, observation)
    observation.latitude = 0
    with pytest.raises(ValueError, match="Coordinates"):
        module.match_observation(saved, observation)
    context.hourly_forecasts = []
    with pytest.raises(ValueError, match="No provider"):
        module.snapshot(context)
