from datetime import datetime, timedelta

from lol_esports_warehouse.riot.client import PersistedClient, LiveStatsClient
from lol_esports_warehouse.riot.schemas.event_details import EventDetail, Game
from lol_esports_warehouse.riot.schemas.leagues import League
from lol_esports_warehouse.riot.schemas.schedule import Schedule, ScheduleEvent
from lol_esports_warehouse.riot.schemas.teams import Team
from lol_esports_warehouse.riot.schemas.tournaments import Tournament
from lol_esports_warehouse.riot.schemas.window import WindowResponse
from lol_esports_warehouse.riot.schemas.details import DetailsResponse
from collections.abc import Callable

_TIME_FMT = r"%Y-%m-%dT%H:%M:%SZ"


class RiotService:
    """Service layer that uses both Riot clients to fetch esports data."""

    def __init__(self, locale: str = "en-US"):
        self._persisted = PersistedClient()
        self._live = LiveStatsClient()
        self._locale = locale

    def get_leagues(self) -> list[League]:
        data = self._persisted.get("/getLeagues", params={"hl": self._locale})
        return [League(**l) for l in data["data"]["leagues"]]

    def get_tournaments_for_league(self, league_id: int) -> list[Tournament]:
        data = self._persisted.get(
            "/getTournamentsForLeague",
            params={"hl": self._locale, "leagueId": league_id},
        )
        return [
            Tournament(**t)
            for league in data["data"]["leagues"]
            for t in league["tournaments"]
        ]

    def _fetch_schedule_page(self, page_token: str | None = None) -> Schedule:
        params: dict = {"hl": self._locale}
        if page_token:
            params["pageToken"] = page_token
        data = self._persisted.get("/getSchedule", params=params)
        schedule = Schedule(**data["data"]["schedule"])
        schedule.events = [e for e in schedule.events if e.type == "match"]
        return schedule

    def fetch_all_schedule(
        self,
        on_page: Callable[[list[ScheduleEvent]], None] | None = None,
        all_exist: Callable[[list[ScheduleEvent]], bool] | None = None,
    ) -> list[ScheduleEvent]:
        """Fetch the full schedule. If all_exist is provided, stops backtracking
        older pages once all events on a page already exist."""
        all_events: list[ScheduleEvent] = []

        def _collect(events: list[ScheduleEvent]) -> None:
            all_events.extend(events)
            if on_page:
                on_page(events)

        # 1. Fetch the current (most recent) page
        current = self._fetch_schedule_page()
        _collect(current.events)

        # 2. Fetch all newer pages
        newer_token = current.pages.newer
        while newer_token:
            page = self._fetch_schedule_page(newer_token)
            _collect(page.events)
            newer_token = page.pages.newer

        # 3. Backtrack through older pages, stop if all events already exist
        older_token = current.pages.older
        while older_token:
            page = self._fetch_schedule_page(older_token)
            if all_exist and all_exist(page.events):
                break
            _collect(page.events)
            older_token = page.pages.older

        return all_events

    def get_event_details(self, match_id: int) -> EventDetail:
        data = self._persisted.get(
            "/getEventDetails",
            params={"hl": self._locale, "id": match_id},
        )
        return EventDetail(**data["data"]["event"])

    def get_games(self, game_ids: list[str]) -> list[Game]:
        data = self._persisted.get(
            "/getGames",
            params={"hl": self._locale, "id": ",".join(game_ids)},
        )
        return [Game(**g) for g in data["data"]["games"]]

    def get_teams(self, team_slugs: list[str] | None = None) -> list[Team]:
        params: dict = {"hl": self._locale}
        if team_slugs:
            params["id"] = ",".join(team_slugs)
        data = self._persisted.get("/getTeams", params=params)
        return [Team(**t) for t in data["data"]["teams"]]

    def fetch_game_window(self, game_id: str) -> WindowResponse | None:
        """Paginate getWindow for a completed game, returning all frames."""
        data = self._live.get_window(game_id)
        if data is None:
            return None
        response = WindowResponse(**data)
        all_frames = list(response.frames)

        # Track request time independently so we always advance, even during pauses
        next_ts = None
        if all_frames:
            next_ts = datetime.strptime(
                all_frames[-1].rfc460Timestamp.split(".")[0].rstrip("Z") + "Z",
                _TIME_FMT,
            )
            next_ts += timedelta(seconds=10 - next_ts.second % 10 + 10)

        while all_frames and all_frames[-1].gameState != "finished":
            data = self._live.get_window(game_id, next_ts.strftime(_TIME_FMT))
            page = WindowResponse(**data)
            if not page.frames:
                break
            all_frames.extend(page.frames)
            next_ts += timedelta(seconds=10)

        response.frames = all_frames
        return response

    def fetch_game_details(self, game_id: str) -> DetailsResponse | None:
        """Paginate getDetails for a completed game, returning all frames."""
        data = self._live.get_details(game_id)
        if data is None:
            return None
        response = DetailsResponse(**data)
        all_frames = list(response.frames)

        next_ts = None
        if all_frames:
            next_ts = datetime.strptime(
                all_frames[-1].rfc460Timestamp.split(".")[0].rstrip("Z") + "Z",
                _TIME_FMT,
            )
            next_ts += timedelta(seconds=10 - next_ts.second % 10 + 10)

        while all_frames:
            data = self._live.get_details(game_id, next_ts.strftime(_TIME_FMT))
            if data is None:
                break
            page = DetailsResponse(**data)
            if not page.frames:
                break
            all_frames.extend(page.frames)
            next_ts += timedelta(seconds=10)

        response.frames = all_frames
        return response

    def close(self) -> None:
        self._persisted.close()
        self._live.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
