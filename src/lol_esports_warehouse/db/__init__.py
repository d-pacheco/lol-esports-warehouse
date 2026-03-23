import psycopg
from psycopg_pool import ConnectionPool

from lol_esports_warehouse.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from lol_esports_warehouse.db.event_dao import EventDAO
from lol_esports_warehouse.db.game_dao import GameDAO
from lol_esports_warehouse.db.league_dao import LeagueDAO
from lol_esports_warehouse.db.schema import SCHEMA
from lol_esports_warehouse.db.team_dao import TeamDAO

_CONNINFO = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"


class Database:
    def __init__(self):
        self._pool = ConnectionPool(conninfo=_CONNINFO, min_size=1, max_size=10)
        self._create_tables()
        self.leagues = LeagueDAO(self._pool)
        self.events = EventDAO(self._pool)
        self.games = GameDAO(self._pool)
        self.teams = TeamDAO(self._pool)

    def _create_tables(self) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    def close(self) -> None:
        self._pool.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
