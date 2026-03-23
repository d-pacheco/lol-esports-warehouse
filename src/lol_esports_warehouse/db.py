from datetime import datetime, timezone

import psycopg

from lol_esports_warehouse.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from lol_esports_warehouse.riot.schemas.event_details import EventDetail, Game
from lol_esports_warehouse.riot.schemas.leagues import League
from lol_esports_warehouse.riot.schemas.schedule import ScheduleEvent
from lol_esports_warehouse.riot.schemas.teams import Team
from lol_esports_warehouse.riot.schemas.tournaments import Tournament
from lol_esports_warehouse.riot.schemas.window import WindowResponse


class Database:
    def __init__(self):
        self._conn = psycopg.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
        )
        self._create_tables()

    def _create_tables(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leagues (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    image TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    region TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tournaments (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    league_id TEXT NOT NULL REFERENCES leagues(id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    match_id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    block_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    type TEXT NOT NULL,
                    league_slug TEXT NOT NULL,
                    league_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    strategy_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_teams (
                    match_id TEXT NOT NULL REFERENCES events(match_id),
                    team_code TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    team_image TEXT NOT NULL,
                    game_wins INTEGER NOT NULL DEFAULT 0,
                    outcome TEXT,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (match_id, team_code)
                );
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL REFERENCES events(match_id),
                    state TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    frames_status TEXT
                );
                CREATE TABLE IF NOT EXISTS game_teams (
                    game_id TEXT NOT NULL REFERENCES games(id),
                    team_id TEXT NOT NULL,
                    side TEXT,
                    PRIMARY KEY (game_id, team_id)
                );
                CREATE TABLE IF NOT EXISTS vods (
                    game_id TEXT NOT NULL REFERENCES games(id),
                    parameter TEXT NOT NULL,
                    locale TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    offset_secs INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (game_id, parameter)
                );
                CREATE TABLE IF NOT EXISTS teams (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    image TEXT NOT NULL DEFAULT '',
                    alternative_image TEXT,
                    home_league_name TEXT NOT NULL DEFAULT '',
                    home_league_region TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL REFERENCES teams(id),
                    summoner_name TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    image TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS game_metadata (
                    game_id TEXT PRIMARY KEY,
                    patch_version TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS game_participant_metadata (
                    game_id TEXT NOT NULL,
                    participant_id INTEGER NOT NULL,
                    esports_team_id TEXT NOT NULL DEFAULT '',
                    team_side TEXT NOT NULL,
                    summoner_name TEXT NOT NULL DEFAULT '',
                    champion_id TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (game_id, participant_id)
                );
                CREATE TABLE IF NOT EXISTS game_team_frames (
                    game_id TEXT NOT NULL,
                    team_side TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    game_state TEXT NOT NULL DEFAULT '',
                    total_gold INTEGER NOT NULL DEFAULT 0,
                    inhibitors INTEGER NOT NULL DEFAULT 0,
                    towers INTEGER NOT NULL DEFAULT 0,
                    barons INTEGER NOT NULL DEFAULT 0,
                    total_kills INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (game_id, team_side, timestamp)
                );
                CREATE TABLE IF NOT EXISTS game_team_frame_dragons (
                    game_id TEXT NOT NULL,
                    dragon_number INTEGER NOT NULL,
                    team_side TEXT NOT NULL,
                    dragon_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (game_id, dragon_number)
                );
            """)
        self._conn.commit()

    def save_leagues(self, leagues: list[League]) -> None:
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

    def save_events(self, events: list[ScheduleEvent]) -> None:
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

    def save_event_details(self, detail: EventDetail) -> None:
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

    def save_teams(self, teams: list[Team]) -> None:
        with self._conn.cursor() as cur:
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
        self._conn.commit()

    def get_match_ids_without_games(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT e.match_id FROM events e LEFT JOIN games g ON e.match_id = g.match_id WHERE g.id IS NULL"
            )
            return [r[0] for r in cur.fetchall()]

    def get_stale_event_match_ids(self) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT match_id FROM events WHERE state IN ('unstarted', 'inProgress') AND start_time < %s",
                (now,),
            )
            return [r[0] for r in cur.fetchall()]

    def get_stale_game_ids(self) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT g.id FROM games g JOIN events e ON g.match_id = e.match_id "
                "WHERE g.state IN ('unstarted', 'inProgress') AND e.start_time < %s",
                (now,),
            )
            return [r[0] for r in cur.fetchall()]

    def update_games(self, games: list[Game]) -> None:
        with self._conn.cursor() as cur:
            for g in games:
                cur.execute("UPDATE games SET state = %s WHERE id = %s", (g.state, g.id))
                for vod in g.vods:
                    cur.execute(
                        "INSERT INTO vods (game_id, parameter, locale, provider, offset_secs) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (game_id, parameter) DO UPDATE SET locale=EXCLUDED.locale, provider=EXCLUDED.provider, offset_secs=EXCLUDED.offset_secs",
                        (g.id, vod.parameter, vod.locale, vod.provider, vod.offset),
                    )
        self._conn.commit()

    def update_event_from_details(self, detail: EventDetail, new_state: str) -> None:
        match_id = detail.id
        with self._conn.cursor() as cur:
            cur.execute("UPDATE events SET state = %s WHERE match_id = %s", (new_state, match_id))
            for t in detail.match.teams:
                game_wins = t.result.gameWins if t.result else 0
                cur.execute(
                    "UPDATE event_teams SET game_wins = %s WHERE match_id = %s AND team_code = %s",
                    (game_wins, match_id, t.code),
                )
        self.save_event_details(detail)

    def all_events_exist(self, events: list[ScheduleEvent]) -> bool:
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

    def get_completed_game_ids_without_frames(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT g.id FROM games g LEFT JOIN game_metadata gm ON g.id = gm.game_id "
                "WHERE g.state = 'completed' AND gm.game_id IS NULL "
                "AND (g.frames_status IS NULL OR g.frames_status != 'unavailable')"
            )
            return [r[0] for r in cur.fetchall()]

    def mark_game_frames_unavailable(self, game_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("UPDATE games SET frames_status = 'unavailable' WHERE id = %s", (game_id,))
        self._conn.commit()

    def save_game_window(self, game_id: str, window: WindowResponse) -> None:
        with self._conn.cursor() as cur:
            cur.execute("UPDATE games SET frames_status = 'available' WHERE id = %s", (game_id,))
            meta = window.gameMetadata
            cur.execute(
                "INSERT INTO game_metadata (game_id, patch_version) VALUES (%s, %s) "
                "ON CONFLICT (game_id) DO UPDATE SET patch_version=EXCLUDED.patch_version",
                (game_id, meta.patchVersion),
            )
            for side, team_meta in [("blue", meta.blueTeamMetadata), ("red", meta.redTeamMetadata)]:
                for p in team_meta.participantMetadata:
                    cur.execute(
                        "INSERT INTO game_participant_metadata "
                        "(game_id, participant_id, esports_team_id, team_side, summoner_name, champion_id, role) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (game_id, participant_id) DO UPDATE SET esports_team_id=EXCLUDED.esports_team_id, team_side=EXCLUDED.team_side, summoner_name=EXCLUDED.summoner_name, champion_id=EXCLUDED.champion_id, role=EXCLUDED.role",
                        (game_id, p.participantId, team_meta.esportsTeamId, side,
                         p.summonerName, p.championId, p.role),
                    )
            dragon_counts: dict[str, int] = {"blue": 0, "red": 0}
            game_dragon_number = 0
            for frame in window.frames:
                for side, team in [("blue", frame.blueTeam), ("red", frame.redTeam)]:
                    cur.execute(
                        "INSERT INTO game_team_frames "
                        "(game_id, team_side, timestamp, game_state, total_gold, inhibitors, towers, barons, total_kills) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (game_id, team_side, timestamp) DO UPDATE SET game_state=EXCLUDED.game_state, total_gold=EXCLUDED.total_gold, inhibitors=EXCLUDED.inhibitors, towers=EXCLUDED.towers, barons=EXCLUDED.barons, total_kills=EXCLUDED.total_kills",
                        (game_id, side, frame.rfc460Timestamp, frame.gameState,
                         team.totalGold, team.inhibitors, team.towers, team.barons, team.totalKills),
                    )
                    if len(team.dragons) > dragon_counts[side]:
                        for i in range(dragon_counts[side], len(team.dragons)):
                            game_dragon_number += 1
                            cur.execute(
                                "INSERT INTO game_team_frame_dragons "
                                "(game_id, dragon_number, team_side, dragon_type, timestamp) "
                                "VALUES (%s, %s, %s, %s, %s) "
                                "ON CONFLICT (game_id, dragon_number) DO UPDATE SET team_side=EXCLUDED.team_side, dragon_type=EXCLUDED.dragon_type, timestamp=EXCLUDED.timestamp",
                                (game_id, game_dragon_number, side, team.dragons[i], frame.rfc460Timestamp),
                            )
                        dragon_counts[side] = len(team.dragons)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
