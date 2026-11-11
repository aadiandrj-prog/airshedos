"""Versioned durable-source allowlist, not a declaration of legal approval.

Real collection requires owner/provider policy review (repository defaults OFF).
Registry keys are immutable version identifiers; revise the key for policy changes.
Raw responses, Google values and Google-dependent derived snapshots have no payload
type in this store. Attribution is resolved from this registry on future projection.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePolicy:
    source: str
    version: str
    max_days: int
    attribution: str
    review_reference: str
    export_allowed: bool = False  # Export permissions require separate review.


POLICIES = {
    "firms_normalized_v1": SourcePolicy(
        "NASA_FIRMS",
        "nasa_firms_v1",
        30,
        "NASA FIRMS / selected VIIRS NRT product",
        "https://www.earthdata.nasa.gov/data/tools/firms/faq",
    ),
    "sentinel_normalized_v1": SourcePolicy(
        "SENTINEL_5P",
        "sentinel_5p_v1",
        30,
        "Copernicus Sentinel-5P / Google Earth Engine delivery",
        "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2",
    ),
    "gemini_normalized_v1": SourcePolicy(
        "GEMINI",
        "gemini_v1",
        30,
        "Google Gemini on Vertex AI; advisory visual interpretation",
        "https://cloud.google.com/vertex-ai/generative-ai/docs/data-governance",
    ),
}
GOOGLE_NO_STORE_POLICY = "google_no_store_v1"
POLICIES.update(
    {
        "firms_normalized_v2": SourcePolicy(
            "NASA_FIRMS",
            "nasa_firms_v2",
            30,
            "NASA FIRMS / selected VIIRS NRT product",
            "https://www.earthdata.nasa.gov/data/tools/firms/faq",
        ),
        "sentinel_normalized_v2": SourcePolicy(
            "SENTINEL_5P",
            "sentinel_5p_v2",
            30,
            "Copernicus Sentinel-5P / Google Earth Engine delivery",
            "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2",
        ),
        "retained_assessment_v1": SourcePolicy(
            "RULES",
            "retained_assessment_v1",
            30,
            "AirshedOS deterministic advisory; retained-source inputs only",
            "docs/seva/IMPLEMENTATION_BLUEPRINT.md#8-private-media-retention-deletion-and-restore",
        ),
    }
)
GOOGLE_POLICY_REFERENCE = "https://cloud.google.com/maps-platform/terms/maps-service-terms"
