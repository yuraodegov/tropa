"""LLM step: Claude picks and orders places from the candidate list only."""
import json

from anthropic import AsyncAnthropic

from .geo import walk_estimate
from .models import Day, Place, PlanRequest, Stop

# Forced tool call = the model must answer with JSON matching this schema
ITINERARY_TOOL = {
    "name": "build_itinerary",
    "description": "Return a walking itinerary built ONLY from the candidate place ids.",
    "input_schema": {
        "type": "object",
        "properties": {
            "days": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "integer"},
                        "title": {"type": "string"},
                        "stops": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "note": {"type": "string"},
                                },
                                "required": ["id", "note"],
                            },
                        },
                    },
                    "required": ["day", "title", "stops"],
                },
            }
        },
        "required": ["days"],
    },
}

SYSTEM_PROMPT = """You are a local city guide planning walking days.
Rules:
- Use ONLY place ids from the candidate list. Never invent places.
- Each day: 5-8 stops, geographically clustered, ordered to minimise walking.
- Put a cafe mid-morning or afternoon and a restaurant around lunch and/or dinner.
- Match the traveller's interests; skip weak candidates.
- Never repeat a place across days.
- "note": one or two practical sentences (what to see/order, tip). Write titles and notes in language: {lang}.
- Do not state opening hours or prices unless they are in the candidate tags."""


def _candidates_payload(places: list[Place]) -> str:
    # Compact JSON lines: fewer tokens than pretty JSON
    rows = [
        {"id": p.id, "name": p.name, "cat": p.category,
         "lat": round(p.lat, 5), "lon": round(p.lon, 5), **p.tags}
        for p in places
    ]
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)


def assemble_days(raw_days: list[dict], places: list[Place]) -> list[Day]:
    """Validate LLM output against real candidates and compute walking distances."""
    by_id = {p.id: p for p in places}
    used: set[str] = set()
    days: list[Day] = []
    for raw in raw_days:
        stops: list[Stop] = []
        prev: Place | None = None
        total_m = 0
        for s in raw.get("stops", []):
            place = by_id.get(s.get("id"))
            # Drop hallucinated or duplicated ids instead of failing the whole plan
            if place is None or place.id in used:
                continue
            used.add(place.id)
            meters, minutes = (0, 0)
            if prev is not None:
                meters, minutes = walk_estimate(prev.lat, prev.lon, place.lat, place.lon)
                total_m += meters
            stops.append(Stop(place=place, note=s.get("note", ""),
                              walk_from_prev_m=meters, walk_from_prev_min=minutes))
            prev = place
        if stops:
            days.append(Day(day=len(days) + 1, title=raw.get("title", ""),
                            stops=stops, total_walk_km=round(total_m / 1000, 1)))
    return days


async def plan_days(client: AsyncAnthropic, model: str,
                    req: PlanRequest, places: list[Place]) -> list[Day]:
    interests = ", ".join(req.interests) or "general sightseeing"
    user_msg = (
        f"City: {req.city}\nDays: {req.days}\nInterests: {interests}\n\n"
        f"Candidates (one JSON per line):\n{_candidates_payload(places)}"
    )
    msg = await client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT.format(lang=req.lang),
        tools=[ITINERARY_TOOL],
        tool_choice={"type": "tool", "name": "build_itinerary"},
        messages=[{"role": "user", "content": user_msg}],
    )
    tool_block = next(b for b in msg.content if b.type == "tool_use")
    return assemble_days(tool_block.input.get("days", []), places)
