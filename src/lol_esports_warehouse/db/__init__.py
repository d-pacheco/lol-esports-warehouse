import psycopg

from lol_esports_warehouse.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from lol_esports_warehouse.db.event_dao import EventDAO
from lol_esports_warehouse.db.game_dao import GameDAO
from lol_esports_warehouse.db.league_dao import LeagueDAO
from lol_esports_warehouse.db.schema import SCHEMA
from lol_esports_warehouse.db.team_dao import TeamDAO


class Database:
    def __init__(self):
        self._conn = psycopg.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
        )
        self._create_tables()
        self.leagues = LeagueDAO(self._conn)
        self.events = EventDAO(self._conn)
        self.games = GameDAO(self._conn)
        self.teams = TeamDAO(self._conn)

    def _create_tables(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
