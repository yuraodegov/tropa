"""Real places from OpenStreetMap: Nominatim (geocoding) + Overpass (POIs)."""
import httpx

from .models import Place

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Public Overpass servers are free and often overloaded (429/502/504),
# so we try mirrors in order until one answers
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Search radius around the city center; tourist cores fit well inside 3 km
RADIUS_M = 3000
# Hard caps keep the LLM prompt small (cost) and focused (quality)
MAX_SIGHTS = 60
MAX_FOOD = 30


class CityNotFound(Exception):
    pass


async def geocode_city(client: httpx.AsyncClient, city: str) -> tuple[float, float, str]:
    """Return (lat, lon, display_name) of the city center."""
    resp = await client.get(NOMINATIM_URL, params={"q": city, "format": "json", "limit": 1})
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise CityNotFound(city)
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]


def _build_query(lat: float, lon: float) -> str:
    around = f"(around:{RADIUS_M},{lat},{lon})"
    # Sights require a wikidata tag: a cheap but effective "is it notable" filter.
    # Food requires a cuisine tag: filters out half-empty entries.
    return f"""
[out:json][timeout:25];
(
  nwr["tourism"~"^(attraction|museum|viewpoint|gallery)$"]["name"]["wikidata"]{around};
  nwr["historic"~"^(monument|castle|ruins|archaeological_site|memorial)$"]["name"]["wikidata"]{around};
  nwr["leisure"="park"]["name"]["wikidata"]{around};
  nwr["amenity"~"^(restaurant|cafe)$"]["name"]["cuisine"]{around};
);
out center tags;
"""


def _category(tags: dict[str, str]) -> str:
    amenity = tags.get("amenity")
    if amenity in ("restaurant", "cafe"):
        return amenity
    tourism = tags.get("tourism")
    if tourism in ("museum", "gallery"):
        return "museum"
    if tourism == "viewpoint":
        return "viewpoint"
    if tags.get("leisure") == "park":
        return "park"
    return "sight"


# Only tags that help the LLM decide; drop the rest to save tokens
_USEFUL_TAGS = ("cuisine", "opening_hours", "historic", "tourism", "wikipedia", "fee")


def parse_overpass(elements: list[dict]) -> list[Place]:
    sights: list[Place] = []
    food: list[Place] = []
    seen_names: set[str] = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        # Ways/relations carry coordinates in "center"
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not name or lat is None or lon is None:
            continue
        # Same object is often mapped twice (node + building way)
        key = name.casefold()
        if key in seen_names:
            continue
        seen_names.add(key)
        place = Place(
            id=f"{el['type']}/{el['id']}",
            name=tags.get("name:en") or name,
            category=_category(tags),
            lat=float(lat),
            lon=float(lon),
            tags={k: tags[k] for k in _USEFUL_TAGS if k in tags},
        )
        (food if place.category in ("restaurant", "cafe") else sights).append(place)
    return sights[:MAX_SIGHTS] + food[:MAX_FOOD]


class PlacesUnavailable(Exception):
    pass


async def fetch_places(client: httpx.AsyncClient, lat: float, lon: float,
                       urls: list[str] | None = None) -> list[Place]:
    """Query Overpass, falling back to the next mirror on overload or network error."""
    query = _build_query(lat, lon)
    errors: list[str] = []
    for url in urls or OVERPASS_URLS:
        try:
            resp = await client.post(url, data={"data": query}, timeout=40)
            # 429 = rate limited, 5xx = overloaded: try the next mirror
            if resp.status_code == 429 or resp.status_code >= 500:
                errors.append(f"{url} -> HTTP {resp.status_code}")
                continue
            resp.raise_for_status()
            return parse_overpass(resp.json().get("elements", []))
        except (httpx.TransportError, ValueError) as e:
            # TransportError = timeout/connection; ValueError = HTML instead of JSON
            errors.append(f"{url} -> {type(e).__name__}")
    raise PlacesUnavailable("; ".join(errors))
