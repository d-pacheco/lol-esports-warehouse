from psycopg import Connection

from lol_esports_warehouse.riot.schemas.leagues import League
from lol_esports_warehouse.riot.schemas.tournaments import Tournament


class LeagueDAO:
    def __init__(self, conn: Connection):
        self._conn = conn

    def save(self, leagues: list[League]) -> None:
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO leagues (id, slug, name, image, priority, region) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET slug=EXCLUDED.slug, name=EXCLUDED.name, image=EXCLUDED.image, priority=EXCLUDED.priority, region=EXCLUDED.region",
                [(l.id, l.slug, l.name, l.image, l.priority, l.region) for l in leagues],
            )
        self._conn.commit()

    def save_tournaments(self, tournaments: list[Tournament], league_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO tournaments (id, slug, start_date, end_date, league_id) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET slug=EXCLUDED.slug, start_date=EXCLUDED.start_date, end_date=EXCLUDED.end_date, league_id=EXCLUDED.league_id",
                [(t.id, t.slug, t.startDate, t.endDate, league_id) for t in tournaments],
            )
        self._conn.commit()
