from datetime import datetime, timezone

from psycopg import Connection

from lol_esports_warehouse.riot.schemas.event_details import EventDetail
from lol_esports_warehouse.riot.schemas.schedule import ScheduleEvent


class EventDAO:
    def __init__(self, conn: Connection):
        self._conn = conn

    def save(self, events: list[ScheduleEvent]) -> None:
        event_rows = []
        team_rows = []
        for e in events:
            event_rows.append((
                e.match.id, e.startTime, e.blockName, e.state, e.type,
                e.league.slug, e.league.name,
                e.match.strategy.type, e.match.strategy.count,
            ))
            for t in e.match.teams:
                team_rows.append((
                    e.match.id, t.code, t.name, t.image,
                    t.result.gameWins if t.result else 0,
                    t.result.outcome if t.result else None,
                    t.record.wins if t.record else 0,
                    t.record.losses if t.record else 0,
                ))

        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO events (match_id, start_time, block_name, state, type, league_slug, league_name, strategy_type, strategy_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (match_id) DO UPDATE SET start_time=EXCLUDED.start_time, block_name=EXCLUDED.block_name, state=EXCLUDED.state, type=EXCLUDED.type, league_slug=EXCLUDED.league_slug, league_name=EXCLUDED.league_name, strategy_type=EXCLUDED.strategy_type, strategy_count=EXCLUDED.strategy_count",
                event_rows,
            )
            cur.executemany(
                "INSERT INTO event_teams (match_id, team_code, team_name, team_image, game_wins, outcome, wins, losses) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (match_id, team_code) DO UPDATE SET team_name=EXCLUDED.team_name, team_image=EXCLUDED.team_image, game_wins=EXCLUDED.game_wins, outcome=EXCLUDED.outcome, wins=EXCLUDED.wins, losses=EXCLUDED.losses",
                team_rows,
            )
        self._conn.commit()

    def save_details(self, detail: EventDetail) -> None:
        match_id = detail.id
        with self._conn.cursor() as cur:
            for game in detail.match.games:
                cur.execute(
                    "INSERT INTO games (id, match_id, state, number) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET state=EXCLUDED.state, number=EXCLUDED.number",
                    (game.id, match_id, game.state, game.number),
                )
                for gt in game.teams:
                    cur.execute(
                        "INSERT INTO game_teams (game_id, team_id, side) VALUES (%s, %s, %s) "
                        "ON CONFLICT (game_id, team_id) DO UPDATE SET side=EXCLUDED.side",
                        (game.id, gt.id, gt.side),
                    )
                for vod in game.vods:
                    cur.execute(
                        "INSERT INTO vods (game_id, parameter, locale, provider, offset_secs) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (game_id, parameter) DO UPDATE SET locale=EXCLUDED.locale, provider=EXCLUDED.provider, offset_secs=EXCLUDED.offset_secs",
                        (game.id, vod.parameter, vod.locale, vod.provider, vod.offset),
                    )
        self._conn.commit()

    def update_from_details(self, detail: EventDetail, new_state: str) -> None:
        match_id = detail.id
        with self._conn.cursor() as cur:
            cur.execute("UPDATE events SET state = %s WHERE match_id = %s", (new_state, match_id))
            for t in detail.match.teams:
                game_wins = t.result.gameWins if t.result else 0
                cur.execute(
                    "UPDATE event_teams SET game_wins = %s WHERE match_id = %s AND team_code = %s",
                    (game_wins, match_id, t.code),
                )
        self.save_details(detail)

    def get_ids_without_games(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT e.match_id FROM events e LEFT JOIN games g ON e.match_id = g.match_id WHERE g.id IS NULL"
            )
            return [r[0] for r in cur.fetchall()]

    def get_stale_match_ids(self) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT match_id FROM events WHERE state IN ('unstarted', 'inProgress') AND start_time < %s",
                (now,),
            )
            return [r[0] for r in cur.fetchall()]

    def all_exist(self, events: list[ScheduleEvent]) -> bool:
        if not events:
            return True
        match_ids = [e.match.id for e in events]
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM events WHERE match_id = ANY(%s)",
                (match_ids,),
            )
            row = cur.fetchone()
        return row[0] == len(match_ids)
