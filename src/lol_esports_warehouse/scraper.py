import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from lol_esports_warehouse.db import Database
from lol_esports_warehouse.riot import RiotService

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self, svc: RiotService, db: Database):
        self._svc = svc
        self._db = db

    def sync_leagues(self) -> None:
        logger.info("Fetching leagues...")
        leagues = self._svc.get_leagues()
        self._db.leagues.save(leagues)
        logger.info("Saved %d leagues", len(leagues))

    def sync_tournaments(self) -> None:
        logger.info("Fetching tournaments...")
        leagues = self._svc.get_leagues()
        for league in leagues:
            tournaments = self._svc.get_tournaments_for_league(int(league.id))
            self._db.leagues.save_tournaments(tournaments, league.id)
            logger.info("League %s — %d tournaments", league.slug, len(tournaments))

    def sync_schedule(self) -> None:
        total = 0

        def on_page(events):
            nonlocal total
            self._db.events.save(events)
            total += len(events)
            logger.info("Saved page (%d events, %d total)", len(events), total)

        logger.info("Fetching schedule...")
        self._svc.fetch_all_schedule(on_page=on_page, all_exist=self._db.events.all_exist)
        logger.info("Schedule sync complete — %d events saved", total)

    def backfill_event_details(self) -> None:
        match_ids = self._db.events.get_ids_without_games()
        if not match_ids:
            logger.info("No events to backfill")
            return
        logger.info("Fetching details for %d matches...", len(match_ids))
        for i, match_id in enumerate(match_ids, 1):
            try:
                detail = self._svc.get_event_details(int(match_id))
                self._db.events.save_details(detail)
                logger.info("[%d/%d] %s — %d games", i, len(match_ids), match_id, len(detail.match.games))
            except Exception:
                logger.error("[%d/%d] %s — failed", i, len(match_ids), match_id, exc_info=True)

    def refresh_stale_events(self) -> None:
        match_ids = self._db.events.get_stale_match_ids()
        if not match_ids:
            logger.info("No stale events to refresh")
            return
        logger.info("Refreshing %d stale events...", len(match_ids))
        for i, match_id in enumerate(match_ids, 1):
            try:
                detail = self._svc.get_event_details(int(match_id))
                new_state = self._infer_event_state(detail)
                self._db.events.update_from_details(detail, new_state)
                logger.info("[%d/%d] %s — %s", i, len(match_ids), match_id, new_state)
            except Exception:
                logger.error("[%d/%d] %s — failed", i, len(match_ids), match_id, exc_info=True)

    def sync_teams(self) -> None:
        logger.info("Fetching teams...")
        teams = self._svc.get_teams()
        self._db.teams.save(teams)
        logger.info("Saved %d teams", len(teams))

    def refresh_stale_games(self) -> None:
        game_ids = self._db.games.get_stale_ids()
        if not game_ids:
            logger.info("No stale games to refresh")
            return
        chunks = [game_ids[i:i + 10] for i in range(0, len(game_ids), 10)]
        logger.info("Refreshing %d stale games in %d batches...", len(game_ids), len(chunks))
        for i, chunk in enumerate(chunks, 1):
            try:
                games = self._svc.get_games(chunk)
                self._db.games.update(games)
                logger.info("[batch %d/%d] updated %d games", i, len(chunks), len(games))
            except Exception:
                logger.error("[batch %d/%d] failed", i, len(chunks), exc_info=True)

    def backfill_game_frames(self, max_workers: int = 5) -> None:
        game_ids = self._db.games.get_completed_ids_without_frames()
        if not game_ids:
            logger.info("No completed games to backfill frames for")
            return
        logger.info("Fetching window frames for %d games (%d workers)...", len(game_ids), max_workers)

        def process_game(game_id: str) -> str:
            window = self._svc.fetch_game_window(game_id)
            if window is None:
                self._db.games.mark_frames_unavailable(game_id)
                return f"{game_id} — unavailable (204)"
            self._db.games.save_window(game_id, window)
            return f"{game_id} — {len(window.frames)} frames"

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(process_game, gid): gid for gid in game_ids}
            for i, future in enumerate(as_completed(futures), 1):
                game_id = futures[future]
                try:
                    result = future.result()
                    logger.info("[%d/%d] %s", i, len(game_ids), result)
                except Exception:
                    logger.error("[%d/%d] %s — failed", i, len(game_ids), game_id, exc_info=True)

    def backfill_game_details(self, max_workers: int = 5) -> None:
        game_ids = self._db.games.get_completed_ids_without_details()
        if not game_ids:
            logger.info("No completed games to backfill details for")
            return
        logger.info("Fetching player details for %d games (%d workers)...", len(game_ids), max_workers)

        def process_game(game_id: str) -> str:
            details = self._svc.fetch_game_details(game_id)
            if details is None:
                self._db.games.mark_details_unavailable(game_id)
                return f"{game_id} — unavailable (204)"
            self._db.games.save_details(game_id, details)
            return f"{game_id} — {len(details.frames)} frames"

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(process_game, gid): gid for gid in game_ids}
            for i, future in enumerate(as_completed(futures), 1):
                game_id = futures[future]
                try:
                    result = future.result()
                    logger.info("[%d/%d] %s", i, len(game_ids), result)
                except Exception:
                    logger.error("[%d/%d] %s — failed", i, len(game_ids), game_id, exc_info=True)

    @staticmethod
    def _infer_event_state(detail) -> str:
        game_states = {g.state for g in detail.match.games}
        if game_states and game_states <= {"completed", "unneeded"}:
            return "completed"
        return "inProgress"
