"""Spherical distances in km for WGS84 latitude/longitude inputs (not a survey tool)."""

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = phi2 - phi1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def bounding_boxes(lat: float, lng: float, radius_km: float) -> list[tuple[float, ...]]:
    """Cover a spherical circle; split at the date line and include all longitudes at poles."""
    angular = radius_km / EARTH_RADIUS_KM
    dlat = math.degrees(angular)
    south, north = max(-90, lat - dlat), min(90, lat + dlat)
    if south == -90 or north == 90:
        return [(-180, south, 180, north)]
    dlng = math.degrees(math.asin(min(1, math.sin(angular) / math.cos(math.radians(lat)))))
    west, east = lng - dlng, lng + dlng
    if west < -180:
        return [(west + 360, south, 180, north), (-180, south, east, north)]
    if east > 180:
        return [(west, south, 180, north), (-180, south, east - 360, north)]
    return [(west, south, east, north)]
