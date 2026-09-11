"""One bounded Earth Engine query batch. No user auth flow, raw EE objects or imagery in the API."""

import asyncio
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.environment.models import (
    EnvironmentalProvenance,
    SatelliteObservation,
    SatelliteProductResult,
    SatelliteQuality,
    SatelliteSearchWindow,
    SourceState,
)

PRODUCTS = {
    "no2": (
        "COPERNICUS/S5P/NRTI/L3_NO2",
        "tropospheric_NO2_column_number_density",
        "mol/m²",
        "Catalog L3 ingestion: tropospheric NO2 QA >= 0.75",
    ),
    "co": (
        "COPERNICUS/S5P/NRTI/L3_CO",
        "CO_column_number_density",
        "mol/m²",
        "Catalog L3 ingestion: CO QA >= 0.50",
    ),
    "aerosol_index": (
        "COPERNICUS/S5P/NRTI/L3_AER_AI",
        "absorbing_aerosol_index",
        "dimensionless",
        "Catalog L3 ingestion: AER_AI QA >= 0.80",
    ),
}
GRID_SCALE_M = 1113.2


def catalog_url(product: str) -> str:
    return "https://developers.google.com/earth-engine/datasets/catalog/" + PRODUCTS[product][
        0
    ].replace("/", "_")


def source_provenance() -> EnvironmentalProvenance:
    return EnvironmentalProvenance(
        source_id="earth_engine_sentinel5p",
        method="Sentinel-5P NRTI L3; independent latest usable scene per product",
        documentation_url="https://developers.google.com/earth-engine/datasets/tags/s5p",
        note=(
            "Copernicus Sentinel-5P / TROPOMI via Google Earth Engine. "
            "Regional atmospheric context, not surface concentration or causal attribution."
        ),
    )


@dataclass(frozen=True)
class SatelliteQuery:
    latitude: float
    longitude: float
    window: SatelliteSearchWindow
    radius_km: float


class SatelliteProvider(Protocol):
    name: str
    configured: bool

    async def fetch(self, query: SatelliteQuery) -> list[SatelliteProductResult]: ...


def absent(product, status, availability, message, latency_ms=0) -> SatelliteProductResult:
    collection, band, unit, _ = PRODUCTS[product]
    return SatelliteProductResult(
        product=product,
        status=status,
        availability=availability,
        message=message,
        collection=collection,
        band=band,
        unit=unit,
        latency_ms=latency_ms,
    )


def normalize(
    product: str, raw: dict, query: SatelliteQuery, retrieved: datetime
) -> SatelliteProductResult:
    collection, band, unit, qa = PRODUCTS[product]
    count, quality_count = raw["scene_count"], raw["quality_scene_count"]
    if type(count) is not int or type(quality_count) is not int or not 0 <= quality_count <= count:
        raise ValueError("Invalid scene counts")
    row = raw["observation"]
    if row is None:
        reason = (
            "no_scene"
            if count == 0
            else "quality_filtered"
            if quality_count == 0
            else "no_usable_pixels"
        )
        messages = {
            "no_scene": "No scene intersects this neighborhood in the search window.",
            "quality_filtered": "No scenes have nominal quality and processing metadata.",
            "no_usable_pixels": (
                "Scenes exist but no valid local pixels remain after masks and filtering. "
                "QA loss and missing coverage cannot be separated in L3."
            ),
        }
        result = absent(product, SourceState.UNAVAILABLE, reason, messages[reason])
    else:
        if type(row["value"]) not in (int, float) or type(row["observed_ms"]) not in (int, float):
            raise ValueError("Expected numeric value and acquisition timestamp")
        if type(row["valid_count"]) is not int:
            raise ValueError("Expected integer valid pixel count")
        value = float(row["value"])
        observed = datetime.fromtimestamp(row["observed_ms"] / 1000, UTC)
        if not math.isfinite(value) or (unit == "mol/m²" and value < -0.001):
            raise ValueError("Invalid column value")
        if not query.window.start <= observed < query.window.end or observed > retrieved:
            raise ValueError("Observation outside requested window")
        if not row["image_id"].startswith(collection + "/") or quality_count == 0:
            raise ValueError("Invalid image identity")
        filters = [
            "Upstream L3 valid-pixel mask",
            "PRODUCT_QUALITY = Nominal",
            "PROCESSING_STATUS = Nominal",
        ]
        if unit == "mol/m²":
            filters.append("Column >= -0.001 mol/m²; retain non-outlier negative values")
        quality = SatelliteQuality(
            catalog_qa_rule=qa,
            scene_quality=row["product_quality"],
            processing_status=row["processing_status"],
            valid_grid_cells=row["valid_count"],
            applied_filters=filters,
        )
        observation = SatelliteObservation(
            product=product,
            value=value,
            unit=unit,
            observed_at=observed,
            retrieved_at=retrieved,
            age_seconds=(retrieved - observed).total_seconds(),
            collection=collection,
            band=band,
            image_id=row["image_id"],
            source_product_id=row.get("product_id"),
            grid_scale_m=GRID_SCALE_M,
            native_footprint=row.get("native_footprint"),
            retrieval_radius_km=query.radius_km,
            quality=quality,
            provenance=EnvironmentalProvenance(
                source_id=row["image_id"],
                method=(
                    "Mean of valid L3 cells within buffered point; "
                    "latest usable scene independently per product"
                ),
                documentation_url=catalog_url(product),
                note=(
                    "Gridded scale is not native sensor footprint. "
                    "L3 QA is pre-applied; no confidence percentage inferred."
                ),
            ),
        )
        result = SatelliteProductResult(
            product=product,
            status=SourceState.LIVE,
            availability="available",
            message="Latest usable satellite observation in the requested window.",
            collection=collection,
            band=band,
            unit=unit,
            observation=observation,
        )
    result.scene_count, result.quality_scene_count = count, quality_count
    return result


class EarthEngineClient:
    """Official Python API, initialized lazily with ADC and one explicit project."""

    def __init__(self, project: str):
        self.project = project
        self.initialized = False

    def query(self, product: str, query: SatelliteQuery) -> dict:
        import ee
        import google.auth
        import httplib2

        if not self.initialized:
            credentials, _ = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/earthengine",
                    "https://www.googleapis.com/auth/cloud-platform",
                ]
            )
            ee.Initialize(
                credentials=credentials,
                project=self.project,
                http_transport=httplib2.Http(timeout=10),
            )
            ee.data.setDeadline(10000)
            ee.data.setMaxRetries(0)
            self.initialized = True
        collection, band, unit, _ = PRODUCTS[product]
        geometry = ee.Geometry.Point([query.longitude, query.latitude]).buffer(
            query.radius_km * 1000
        )
        scenes = (
            ee.ImageCollection(collection)
            .filterBounds(geometry)
            .filterDate(query.window.start.isoformat(), query.window.end.isoformat())
        )
        nominal = scenes.filter(ee.Filter.eq("PRODUCT_QUALITY", "Nominal")).filter(
            ee.Filter.eq("PROCESSING_STATUS", "Nominal")
        )

        def summarize(image):
            image = ee.Image(image)
            values = image.select(band).rename("value")
            if unit == "mol/m²":
                values = values.updateMask(values.gte(-0.001))
            stats = values.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                geometry=geometry,
                scale=GRID_SCALE_M,
                maxPixels=100000,
                bestEffort=False,
            )
            return ee.Feature(
                None,
                {
                    "value": stats.get("value_mean"),
                    "valid_count": stats.get("value_count"),
                    "observed_ms": image.get("system:time_start"),
                    "image_id": ee.String(collection + "/").cat(image.get("system:index")),
                    "product_id": image.get("PRODUCT_ID"),
                    "product_quality": image.get("PRODUCT_QUALITY"),
                    "processing_status": image.get("PROCESSING_STATUS"),
                    "native_footprint": image.get("SPATIAL_RESOLUTION"),
                },
            )

        # toList requires a positive count even for an empty collection.
        candidates = ee.FeatureCollection(nominal.toList(nominal.size().max(1)).map(summarize))
        usable = (
            candidates.filter(ee.Filter.notNull(["value"]))
            .filter(ee.Filter.gt("valid_count", 0))
            .sort("observed_ms", False)
        )
        # Only counts and the single most recent usable scene leave Earth Engine.
        return ee.Dictionary(
            {
                "scene_count": scenes.size(),
                "quality_scene_count": nominal.size(),
                "observation": ee.Algorithms.If(
                    usable.size().gt(0), ee.Feature(usable.first()).toDictionary(), None
                ),
            }
        ).getInfo()


def classify_error(exc: Exception):
    from google.auth.exceptions import DefaultCredentialsError, RefreshError

    if isinstance(exc, DefaultCredentialsError):
        return (
            SourceState.NOT_CONFIGURED,
            "not_configured",
            "Application Default Credentials are missing or unreadable. Configure backend ADC.",
        )
    if isinstance(exc, RefreshError):
        return (
            SourceState.ERROR,
            "authentication_error",
            "Earth Engine credentials could not be refreshed. Renew backend ADC.",
        )
    # Classification uses text internally; raw exceptions may contain tokens/URLs and never escape.
    message = str(exc).lower()
    if any(
        word in message
        for word in (
            "not registered",
            "not enabled",
            "has not been used",
            "service_disabled",
            "project is required",
        )
    ):
        return (
            SourceState.ERROR,
            "configuration_error",
            "Earth Engine project must be enabled and registered for access.",
        )
    if any(
        word in message
        for word in ("permission", "unauthorized", "403", "401", "credentials", "authentication")
    ):
        return (
            SourceState.ERROR,
            "authentication_error",
            "Earth Engine denied authentication or project permissions.",
        )
    if isinstance(exc, TimeoutError) or "timed out" in message or "deadline" in message:
        return SourceState.UNAVAILABLE, "timeout", "Earth Engine request timed out."
    return (
        SourceState.ERROR,
        "provider_error",
        "Earth Engine query failed or returned an invalid result.",
    )


class EarthEngineSentinel5PProvider:
    name = "earth_engine_sentinel5p"

    def __init__(self, project: str, timeout_seconds=25, client=None):
        self.configured = bool(project)
        self.timeout_seconds = timeout_seconds
        self.client = client or EarthEngineClient(project)
        self.active_task = None

    def _run(self, query, results, deadline):
        for product in PRODUCTS:
            if time.monotonic() >= deadline:
                break
            started = time.perf_counter()
            try:
                raw = self.client.query(product, query)
                result = normalize(product, raw, query, datetime.now(UTC))
            except Exception as exc:
                status, reason, message = classify_error(exc)
                result = absent(product, status, reason, message)
            result.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            results[product] = result
            if result.availability in (
                "not_configured",
                "authentication_error",
                "configuration_error",
            ):
                for remaining in PRODUCTS:
                    results.setdefault(
                        remaining,
                        absent(remaining, result.status, result.availability, result.message),
                    )
                break

    async def fetch(self, query: SatelliteQuery) -> list[SatelliteProductResult]:
        if not self.configured:
            return [
                absent(
                    p,
                    SourceState.NOT_CONFIGURED,
                    "not_configured",
                    "Set EARTH_ENGINE_PROJECT (or GOOGLE_CLOUD_PROJECT) and configure backend ADC.",
                )
                for p in PRODUCTS
            ]
        if self.active_task and not self.active_task.done():
            return [
                absent(
                    p,
                    SourceState.UNAVAILABLE,
                    "busy",
                    "A previous Earth Engine request is still ending; retry shortly.",
                )
                for p in PRODUCTS
            ]
        started = time.perf_counter()
        results = {}
        self.active_task = asyncio.create_task(
            asyncio.to_thread(self._run, query, results, time.monotonic() + self.timeout_seconds)
        )
        try:
            await asyncio.wait_for(asyncio.shield(self.active_task), self.timeout_seconds)
        except TimeoutError:
            pass
        # A timed-out sync RPC cannot be killed. Keep the single task reserved until it ends;
        # never enqueue another batch behind it, and retain already completed products.
        snapshot = dict(results)
        return [
            snapshot.get(p)
            or absent(
                p,
                SourceState.UNAVAILABLE,
                "timeout",
                "Satellite lookup deadline exceeded; other completed products are retained.",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            for p in PRODUCTS
        ]
