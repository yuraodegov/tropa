"""Distance helpers. Straight-line distance times a factor approximates walking."""
import math

EARTH_RADIUS_M = 6_371_000
# City streets are not straight lines; ~1.3 is a common detour factor
WALK_DETOUR_FACTOR = 1.3
WALK_SPEED_M_PER_MIN = 80  # ~4.8 km/h


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def walk_estimate(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[int, int]:
    """Return (meters, minutes) of an estimated walk between two points."""
    meters = haversine_m(lat1, lon1, lat2, lon2) * WALK_DETOUR_FACTOR
    minutes = max(1, round(meters / WALK_SPEED_M_PER_MIN))
    return round(meters), minutes
