from psycopg_pool import ConnectionPool

from lol_esports_warehouse.riot.schemas.teams import Team


class TeamDAO:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def save(self, teams: list[Team]) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                for t in teams:
                    cur.execute(
                        "INSERT INTO teams (id, slug, name, code, image, alternative_image, home_league_name, home_league_region) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (id) DO UPDATE SET slug=EXCLUDED.slug, name=EXCLUDED.name, code=EXCLUDED.code, image=EXCLUDED.image, alternative_image=EXCLUDED.alternative_image, home_league_name=EXCLUDED.home_league_name, home_league_region=EXCLUDED.home_league_region",
                        (t.id, t.slug, t.name, t.code, t.image, t.alternativeImage or None,
                         t.homeLeague.name if t.homeLeague else "",
                         t.homeLeague.region if t.homeLeague else ""),
                    )
                    for p in t.players:
                        cur.execute(
                            "INSERT INTO players (id, team_id, summoner_name, first_name, last_name, image, role) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (id) DO UPDATE SET team_id=EXCLUDED.team_id, summoner_name=EXCLUDED.summoner_name, first_name=EXCLUDED.first_name, last_name=EXCLUDED.last_name, image=EXCLUDED.image, role=EXCLUDED.role",
                            (p.id, t.id, p.summonerName, p.firstName, p.lastName, p.image, p.role),
                        )
            conn.commit()
