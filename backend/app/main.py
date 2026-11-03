"""FastAPI entry point: POST /plan builds a walking itinerary for a city."""
import os

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from .models import PlanRequest, PlanResponse
from .places import CityNotFound, PlacesUnavailable, fetch_places, geocode_city
from .planner import plan_days

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
USER_AGENT = os.getenv("USER_AGENT", "TropaPlanner/0.1")

app = FastAPI(title="Tropa planner", version="0.1.0")
llm = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse)
async def plan(req: PlanRequest) -> PlanResponse:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20) as http:
        try:
            lat, lon, _ = await geocode_city(http, req.city)
        except CityNotFound:
            raise HTTPException(404, f"City not found: {req.city}")
        try:
            places = await fetch_places(http, lat, lon)
        except (PlacesUnavailable, httpx.HTTPError) as e:
            # All Overpass mirrors failed; the message lists each one's error
            raise HTTPException(503, f"Places service unavailable: {e}")

    if len(places) < 5:
        raise HTTPException(422, "Too few places found for this city")

    days = await plan_days(llm, MODEL, req, places)
    return PlanResponse(city=req.city, center_lat=lat, center_lon=lon,
                        days=days, candidates_count=len(places))
