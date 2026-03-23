from lol_esports_warehouse.db import Database
from lol_esports_warehouse.log_config import setup_logging
from lol_esports_warehouse.riot import RiotService
from lol_esports_warehouse.scraper import Scraper


def main() -> None:
    setup_logging()
    with RiotService() as svc, Database() as db:
        scraper = Scraper(svc, db)
        # scraper.sync_schedule()
        # scraper.backfill_event_details()
        scraper.refresh_stale_events()
        scraper.refresh_stale_games()
        scraper.backfill_game_frames()
        # scraper.sync_teams()


if __name__ == "__main__":
    main()
