from lol_esports_warehouse.db import Database
from lol_esports_warehouse.log_config import setup_logging
from lol_esports_warehouse.riot import RiotService
from lol_esports_warehouse.scraper import Scraper


def main() -> None:
    setup_logging()
    with RiotService() as svc, Database() as db:
        scraper = Scraper(svc, db)
        # scraper.sync_leagues()
        # scraper.sync_tournaments()
        # sync_teams must run before any game data is saved — game_teams.team_id FKs to teams(id)
        # scraper.sync_teams()
        scraper.sync_schedule()
        scraper.backfill_event_details()
        # scraper.refresh_stale_events()
        # scraper.refresh_stale_games()
        # scraper.backfill_game_frames()


if __name__ == "__main__":
    main()
