# LoL Esports Warehouse

Fetch professional esports game data from the Riot Games API.

## Setup

```bash
# Start PostgreSQL
docker compose up -d

# Python environment
python3 -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add your Riot API key and database credentials.

## Usage

```bash
python -m lol_esports_warehouse.main
```

## Project Structure

```
src/lol_esports_warehouse/
├── __init__.py
├── config.py                  # Loads .env, exposes RIOT_API_KEY
├── log_config.py              # JSON file + console logging (JsonFormatter)
├── main.py                    # Entry point — thin wiring only
├── scraper.py                 # Business logic & orchestration (Scraper class)
├── db/                        # PostgreSQL database layer (DAO pattern)
│   ├── __init__.py            # Database class — connection, schema, composes DAOs
│   ├── schema.py              # CREATE TABLE DDL
│   ├── league_dao.py          # LeagueDAO — leagues + tournaments
│   ├── event_dao.py           # EventDAO — events, event_teams, event details
│   ├── game_dao.py            # GameDAO — games, game_teams, vods, frames
│   └── team_dao.py            # TeamDAO — teams + players
├── riot/                      # Sub-package for all Riot API interaction
│   ├── __init__.py            # Exports PersistedClient, LiveStatsClient, RiotService
│   ├── client.py              # Two HTTP clients (PersistedClient, LiveStatsClient)
│   ├── service.py             # RiotService — high-level methods using both clients
│   └── schemas/               # Pydantic models for API responses
│       ├── __init__.py
│       ├── leagues.py         # League model
│       ├── tournaments.py     # Tournament model
│       ├── schedule.py        # ScheduleEvent, Match, EventTeam, etc.
│       ├── event_details.py   # EventDetail, EventDetailTournament, Game, GameTeam, Vod, Stream
│       ├── teams.py           # Team, Player, HomeLeague
│       └── window.py          # WindowResponse, WindowFrame, WindowTeamStats, GameMetadata, ParticipantMetadata
```

## Architecture

```
client.py    → HTTP transport
service.py   → API endpoint mapping + deserialization
scraper.py   → business logic + orchestration
db/          → persistence (DAO pattern)
main.py      → entry point (wiring only)
```

### Clients (`riot/client.py`)

Two HTTP clients sharing a `_BaseClient` base class:

- **PersistedClient** — `https://esports-api.lolesports.com/persisted/gw` (leagues, tournaments, schedule, event details, games, teams)
- **LiveStatsClient** — `https://feed.lolesports.com/livestats/v1` (live game window data for completed games)

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
- `get_event_details(match_id)` → `EventDetail` — fetches individual games, team sides, vods, streams, tournament ID, and league ID for a match
- `get_games(game_ids)` → `list[Game]` — fetches game state and vods for one or more game IDs
- `get_teams(team_slugs?)` → `list[Team]` — fetches teams with player rosters. Pass no args to fetch all teams, or a list of slugs to fetch specific ones.
- `fetch_game_window(game_id)` → `WindowResponse | None` — paginates the LiveStats `getWindow` endpoint for a completed game, collecting all frames. Returns `None` (204) if data is unavailable.

### Scraper (`scraper.py`)

`Scraper` takes a `RiotService` and `Database` and owns all business logic. Each method is a standalone operation, designed to be called independently (e.g. on separate cron schedules):

- `sync_leagues()` — fetches and saves all leagues
- `sync_tournaments()` — fetches and saves tournaments for each league
- `sync_teams()` — fetches and saves all teams with player rosters. **Must run before any game data is saved** — `game_teams.team_id` FKs to `teams(id)`.
- `sync_schedule()` — fetches the full schedule with incremental sync support. Non-match events (e.g. `show` type) are filtered out during fetch.
- `backfill_event_details()` — fetches details for events that don't have game data yet. Also populates `league_id`, `tournament_id` on events and `team_id` on event_teams.
- `refresh_stale_events()` — re-fetches event details for events with past start times that are still `unstarted` or `inProgress`, infers the new event state from game states, and updates event_teams game_wins
- `refresh_stale_games()` — re-fetches game data (state + vods) for games that are still `unstarted` or `inProgress` with past event start times, in batches of 10
- `backfill_game_frames(max_workers=5)` — fetches live stats window data for completed games that don't have frame data yet, using a thread pool. Saves game metadata, participant metadata, team frames, and dragon events. Marks games as `unavailable` if the API returns 204.

#### Execution Order

The `main.py` entry point runs operations in this order:

1. `sync_leagues` → `sync_tournaments` → `sync_teams` → `sync_schedule` → `backfill_event_details` → `refresh_stale_events` → `refresh_stale_games` → `backfill_game_frames`

`sync_teams` must run before game data operations due to the `game_teams.team_id` FK constraint.

#### State Inference

The `getEventDetails` API does not return an event-level `state` field. The scraper infers it from game states:
- All games `completed` or `unneeded` → event is `completed`
- Otherwise → event is `inProgress`

This logic lives in `Scraper._infer_event_state()`, not in the database layer.

### Schemas (`riot/schemas/`)

Pydantic `BaseModel` classes matching the API response shapes. Field names use camelCase to match the API directly (e.g. `startDate`, `gameWins`).

- **leagues.py**: `League` (id, slug, name, image, region)
- **tournaments.py**: `Tournament` (id, slug, startDate, endDate)
- **schedule.py**: `Schedule`, `ScheduleEvent`, `Match`, `EventTeam`, `TeamResult`, `TeamRecord`, `MatchStrategy`, `EventLeague`, `SchedulePages`
- **event_details.py**: `EventDetail`, `EventDetailTournament`, `EventDetailLeague`, `EventDetailMatch`, `EventDetailTeam`, `Game`, `GameTeam`, `Vod`, `Stream`
- **teams.py**: `Team`, `Player`, `HomeLeague`
- **window.py**: `WindowResponse`, `WindowFrame`, `WindowTeamStats`, `GameMetadata`, `TeamMetadata`, `ParticipantMetadata`

### Database (`db/`)

PostgreSQL via `psycopg` (v3) with connection pooling (`psycopg_pool`). Connection configured via env vars (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`). Uses a DAO pattern with `LeagueDAO`, `EventDAO`, `GameDAO`, and `TeamDAO`.

Tables (created in FK-safe order):

- **leagues** — PK: `id`
- **tournaments** — PK: `id`, FK: `league_id` → leagues
- **teams** — PK: `id`, stores slug, name, code, image, alternative_image (nullable), home league info
- **events** — PK: `match_id`, FK: `league_id` → leagues (nullable), FK: `tournament_id` → tournaments (nullable), stores start_time, state, block_name, strategy
- **event_teams** — PK: `(match_id, team_code)`, FK: `match_id` → events, FK: `team_id` → teams (nullable), stores results/record
- **games** — PK: `id`, FK: `match_id` → events, stores state, game number, frames_status
- **game_teams** — PK: `(game_id, team_id)`, FK: `game_id` → games, FK: `team_id` → teams, stores side (blue/red, nullable)
- **vods** — PK: `(game_id, parameter)`, FK: `game_id` → games, stores vod info
- **players** — PK: `id`, FK: `team_id` → teams, stores summoner_name, first/last name, image, role
- **game_metadata** — PK: `game_id`, FK: `game_id` → games, stores patch_version
- **game_participant_metadata** — PK: `(game_id, participant_id)`, FK: `game_id` → games, stores champion, role, team side, summoner name
- **game_team_frames** — PK: `(game_id, team_side, timestamp)`, FK: `game_id` → games, stores gold, towers, kills, inhibitors, barons per team per timestamp
- **game_team_frame_dragons** — PK: `(game_id, dragon_number)`, FK: `game_id` → games, stores dragon type, team side, timestamp

`league_id`, `tournament_id` on events and `team_id` on event_teams are nullable because they are populated by `backfill_event_details` (from the `getEventDetails` API), not from the schedule endpoint. TBD teams (team ID `"0"`) are skipped during event detail saves — the team FKs on `event_teams` and `game_teams` remain unpopulated until teams are determined and the event is refreshed.

All inserts use `INSERT ... ON CONFLICT DO UPDATE` (upsert) so re-runs are safe.

### Incremental Schedule Sync

The schedule fetcher supports incremental sync:
- First run (empty DB): fetches the full schedule history (all older + newer pages)
- Subsequent runs: fetches current + newer pages, backtracks older pages but stops as soon as it hits a page where all events already exist in the DB

### Event Details Backfill

`get_ids_without_games()` queries for events that don't have corresponding game data yet. The scraper iterates these and fetches/saves details one by one, with error handling per match so failures don't stop the run.

### Stale Data Refresh

Two refresh operations keep the database current:

1. **Stale events** — Events with past start times still marked `unstarted` or `inProgress` are re-fetched via `getEventDetails`. The event state is inferred from game states, team game_wins are updated, and games/game_teams/vods are saved.

2. **Stale games** — Games with state `unstarted` or `inProgress` (whose parent event has a past start time) are re-fetched via `getGames` in batches of 10. Game state and vods are updated. Once a game reaches `completed` (or `unneeded`), it won't be checked again.

### Game Frames Backfill

`backfill_game_frames` fetches live stats window data for completed games using the LiveStats API. For each game:
- Paginates through all window frames until `gameState` is `finished`
- Saves game metadata (patch version), participant metadata (champion, role, side), team frames (gold, towers, kills, etc.), and dragon events
- Uses a thread pool (default 5 workers) for parallel fetching
- Tracks `frames_status` on the games table: `NULL` = not yet fetched, `available` = frames saved, `unavailable` = API returned 204

## API Reference

Using the unofficial lolesports API docs: https://vickz84259.github.io/lolesports-api-docs/

## What's Left / TODO

- [ ] LiveStatsClient `getDetails` endpoint (per-participant frame data)
- [ ] getStandings endpoint
- [ ] Error handling / retries for API calls
- [ ] CLI arguments (e.g. pick which data to fetch, specify DB path) for cron scheduling
- [ ] Frame post-processing
