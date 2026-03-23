# RiotScraper

Fetch professional esports game data from the Riot Games API.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add your Riot API key.

## Usage

```bash
python -m riot_scraper.main
```

## Project Structure

```
src/riot_scraper/
├── __init__.py
├── config.py                  # Loads .env, exposes RIOT_API_KEY
├── main.py                    # Entry point — thin wiring only
├── scraper.py                 # Business logic & orchestration (Scraper class)
├── db.py                      # SQLite database layer
├── riot/                      # Sub-package for all Riot API interaction
│   ├── __init__.py            # Exports PersistedClient, LiveStatsClient, RiotService
│   ├── client.py              # Two HTTP clients (PersistedClient, LiveStatsClient)
│   ├── service.py             # RiotService — high-level methods using both clients
│   └── schemas/               # Pydantic models for API responses
│       ├── __init__.py
│       ├── leagues.py         # League model
│       ├── tournaments.py     # Tournament model
│       ├── schedule.py        # ScheduleEvent, Match, EventTeam, etc.
│       ├── event_details.py   # EventDetail, Game, GameTeam, Vod, Stream
│       └── teams.py           # Team, Player, HomeLeague
```

## Architecture

```
client.py    → HTTP transport
service.py   → API endpoint mapping + deserialization
scraper.py   → business logic + orchestration
db.py        → persistence
main.py      → entry point (wiring only)
```

### Clients (`riot/client.py`)

Two HTTP clients sharing a `_BaseClient` base class:

- **PersistedClient** — `https://esports-api.lolesports.com/persisted/gw` (leagues, tournaments, schedule, event details, games, teams)
- **LiveStatsClient** — `https://feed.lolesports.com/livestats/v1` (live game data, not yet implemented)

Both use the public esports API key and send `Origin`/`Referrer` headers for lolesports.com.

### Service (`riot/service.py`)

`RiotService` wraps both clients and provides:

- `get_leagues()` → `list[League]`
- `get_tournaments_for_league(league_id)` → `list[Tournament]`
- `fetch_all_schedule(on_page, all_exist)` → `list[ScheduleEvent]` — paginates through the schedule:
  1. Fetches current page (no token = most recent)
  2. Follows `newer` page tokens forward until null
  3. Follows `older` page tokens backward until null, or until `all_exist` callback returns True (incremental sync)
  - `on_page` callback is called per page so events can be saved immediately
- `get_event_details(match_id)` → `EventDetail` — fetches individual games, team sides, vods, and streams for a match
- `get_games(game_ids)` → `list[Game]` — fetches game state and vods for one or more game IDs
- `get_teams(team_slugs?)` → `list[Team]` — fetches teams with player rosters. Pass no args to fetch all teams, or a list of slugs to fetch specific ones.

### Scraper (`scraper.py`)

`Scraper` takes a `RiotService` and `Database` and owns all business logic. Each method is a standalone operation, designed to be called independently (e.g. on separate cron schedules):

- `sync_schedule()` — fetches the full schedule with incremental sync support
- `backfill_event_details()` — fetches details for events that don't have game data yet
- `refresh_stale_events()` — re-fetches event details for events with past start times that are still `unstarted` or `inProgress`, infers the new event state from game states, and updates event_teams game_wins
- `refresh_stale_games()` — re-fetches game data (state + vods) for games that are still `unstarted` or `inProgress` with past event start times, in batches of 10
- `sync_teams()` — fetches and saves all teams with player rosters

#### State Inference

The `getEventDetails` API does not return an event-level `state` field. The scraper infers it from game states:
- All games `completed` or `unneeded` → event is `completed`
- Otherwise → event is `inProgress`

This logic lives in `Scraper._infer_event_state()`, not in the database layer.

### Schemas (`riot/schemas/`)

Pydantic `BaseModel` classes matching the API response shapes. Field names use camelCase to match the API directly (e.g. `startDate`, `gameWins`).

- **leagues.py**: `League` (id, slug, name, image, priority, region)
- **tournaments.py**: `Tournament` (id, slug, startDate, endDate)
- **schedule.py**: `Schedule`, `ScheduleEvent`, `Match`, `EventTeam`, `TeamResult`, `TeamRecord`, `MatchStrategy`, `EventLeague`, `SchedulePages`
- **event_details.py**: `EventDetail`, `EventDetailMatch`, `EventDetailTeam`, `Game`, `GameTeam`, `Vod`, `Stream`
- **teams.py**: `Team`, `Player`, `HomeLeague`

### Database (`db.py`)

SQLite via stdlib `sqlite3`. Default file: `riot_scraper.db`. Tables:

- **leagues** — PK: `id`
- **tournaments** — PK: `id`, FK: `league_id` → leagues
- **events** — PK: `match_id`, stores start_time, state, league info, strategy
- **event_teams** — PK: `(match_id, team_code)`, FK: `match_id` → events, stores results/record
- **games** — PK: `id`, FK: `match_id` → events, stores state and game number
- **game_teams** — PK: `(game_id, team_id)`, FK: `game_id` → games, stores side (blue/red, nullable)
- **vods** — PK: `(game_id, parameter)`, FK: `game_id` → games, stores vod info
- **teams** — PK: `id`, stores slug, name, code, image, alternative_image (nullable), home league info
- **players** — PK: `id`, FK: `team_id` → teams, stores summoner_name, first/last name, image, role

All inserts use `INSERT OR REPLACE` so re-runs are safe.

Key DB methods:
- `save_leagues()`, `save_tournaments()`, `save_events()`, `save_event_details()`, `save_teams()`
- `all_events_exist(events)` — checks if all events on a schedule page are already in the DB (used for incremental sync)
- `get_match_ids_without_games()` — finds events that haven't had their details fetched yet
- `get_stale_event_match_ids()` — finds events with state `unstarted`/`inProgress` and past start times
- `get_stale_game_ids()` — finds games with state `unstarted`/`inProgress` whose parent event has a past start time
- `update_event_from_details(detail, new_state)` — updates event state, team game_wins, and saves games/game_teams/vods
- `update_games(games)` — updates game state and upserts vods

### Incremental Schedule Sync

The schedule fetcher supports incremental sync:
- First run (empty DB): fetches the full schedule history (all older + newer pages)
- Subsequent runs: fetches current + newer pages, backtracks older pages but stops as soon as it hits a page where all events already exist in the DB

### Event Details Backfill

`get_match_ids_without_games()` queries for events that don't have corresponding game data yet. The scraper iterates these and fetches/saves details one by one, with error handling per match so failures don't stop the run.

### Stale Data Refresh

Two refresh operations keep the database current:

1. **Stale events** — Events with past start times still marked `unstarted` or `inProgress` are re-fetched via `getEventDetails`. The event state is inferred from game states, team game_wins are updated, and games/game_teams/vods are saved.

2. **Stale games** — Games with state `unstarted` or `inProgress` (whose parent event has a past start time) are re-fetched via `getGames` in batches of 10. Game state and vods are updated. Once a game reaches `completed` (or `unneeded`), it won't be checked again.

## API Reference

Using the unofficial lolesports API docs: https://vickz84259.github.io/lolesports-api-docs/

## What's Left / TODO

- [ ] LiveStatsClient methods not yet implemented (getWindow, getDetails)
- [ ] getStandings endpoint
- [ ] Error handling / retries for API calls
- [ ] CLI arguments (e.g. pick which data to fetch, specify DB path) for cron scheduling
- [ ] frame post-processing
