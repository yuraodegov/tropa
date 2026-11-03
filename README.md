# Tropa — AI city walk planner (working name)

Tell the app a city, number of days and interests — get a day-by-day walking
route on a map: sights, cafes, restaurants, in a sensible order.

## Core idea (anti-hallucination)

The LLM never invents places. The pipeline is:

1. **Real places first** — geocode the city (Nominatim), pull real POIs (Overpass / OpenStreetMap).
2. **LLM only picks and orders** — Claude gets the candidate list with IDs and must
   return a plan that references those IDs only (forced tool call = strict JSON).
3. **Server validates** — unknown IDs are dropped, distances are computed by code, not by the LLM.

## Architecture

```
Android app (Kotlin + Compose + map)
        │  HTTPS, JSON
        ▼
Backend (Python FastAPI)  ── holds all API keys, never in the APK
   ├── places.py   Nominatim + Overpass  → candidate POIs
   ├── planner.py  Claude (tool use)     → ordered days
   └── geo.py      distances, walking time
```

## Stack decisions (MVP)

| Part      | Choice                       | Why                                              |
|-----------|------------------------------|--------------------------------------------------|
| Places    | OpenStreetMap (Overpass)     | Free, no key, data may be stored/cached          |
| LLM       | Claude API                   | Already have a Console account + spend limit     |
| Backend   | Python FastAPI               | Fast to write, easy to test locally with curl    |
| Routing   | Straight-line + walk factor  | Good enough for MVP; real routing in phase 4     |
| Android   | Kotlin + Compose + MapLibre  | Same stack as Sortes; MapLibre fits OSM data     |
| Hosting   | Local → Cloud Run / Render   | Deploy only when the app needs it from the phone |

Known MVP weakness: OSM has no ratings/reviews, so restaurant picks are "real
but not curated". Phase 5 may add Foursquare/Google Places if this hurts.

## Phases

- [x] **Phase 1 — Backend core.** `POST /plan` returns a JSON itinerary. Tested with curl/Swagger.
- [ ] **Phase 2 — Android skeleton.** Compose screen: city, days, interests → call backend → list of days.
- [ ] **Phase 3 — Map.** MapLibre map with numbered markers and a line per day; tap marker → card.
- [ ] **Phase 4 — Real walking routes.** OSRM/GraphHopper for paths and times between stops.
- [ ] **Phase 5 — Polish.** Save trips (Room), offline cache, cost protection (daily cap), deploy, CI APK build.
- [ ] **Phase 6 — The "feature" (фишка).** To be chosen after using the MVP on a real walk.

## Run the backend locally (Windows, PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then put your ANTHROPIC_API_KEY in .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs — Swagger UI, try `POST /plan`.

```powershell
curl.exe -X POST http://127.0.0.1:8000/plan -H "Content-Type: application/json" `
  -d '{\"city\":\"Rome\",\"days\":2,\"interests\":[\"history\",\"food\"],\"lang\":\"ru\"}'
```

Tests: `pytest` (offline, no keys needed).
