"""GIS calculation utilities for distance and propagation.

Used by GISAgent and PropagationAgent; no database dependency.
"""

from __future__ import annotations

import math
from typing import Any


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Distance in km between two WGS84 points (haversine formula)."""
    R = 6371.0  # Earth radius km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def suggest_bands_for_distance_km(distance_km: float) -> list[str]:
    """Suggest ham bands suitable for a given distance (simplified propagation)."""
    if distance_km < 50:
        return ["2m", "70cm"]
    if distance_km < 500:
        return ["6m", "2m", "10m", "20m"]
    if distance_km < 3000:
        return ["20m", "40m", "15m"]
    return ["20m", "40m", "15m", "10m"]


def propagation_note(distance_km: float) -> str:
    """Short human-readable propagation note for distance."""
    if distance_km < 50:
        return "Short range; VHF/UHF suitable."
    if distance_km < 500:
        return "Medium range; 6m/10m/20m may work."
    if distance_km < 3000:
        return "Long range; HF recommended."
    return "Very long range; HF with possible long path."


def propagation_prediction(
    lat_origin: float,
    lon_origin: float,
    lat_dest: float,
    lon_dest: float,
) -> dict[str, Any]:
    """Compute distance and band suggestions between two points."""
    distance_km = haversine_km(lat_origin, lon_origin, lat_dest, lon_dest)
    return {
        "distance_km": round(distance_km, 2),
        "suggested_bands": suggest_bands_for_distance_km(distance_km),
        "notes": propagation_note(distance_km),
    }
