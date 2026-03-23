from datetime import datetime, timezone

from psycopg import Connection

from lol_esports_warehouse.riot.schemas.event_details import Game
from lol_esports_warehouse.riot.schemas.window import WindowResponse


class GameDAO:
    def __init__(self, conn: Connection):
        self._conn = conn

    def update(self, games: list[Game]) -> None:
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

    def get_stale_ids(self) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT g.id FROM games g JOIN events e ON g.match_id = e.match_id "
                "WHERE g.state IN ('unstarted', 'inProgress') AND e.start_time < %s",
                (now,),
            )
            return [r[0] for r in cur.fetchall()]

    def get_completed_ids_without_frames(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT g.id FROM games g LEFT JOIN game_metadata gm ON g.id = gm.game_id "
                "WHERE g.state = 'completed' AND gm.game_id IS NULL "
                "AND (g.frames_status IS NULL OR g.frames_status != 'unavailable')"
            )
            return [r[0] for r in cur.fetchall()]

    def mark_frames_unavailable(self, game_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("UPDATE games SET frames_status = 'unavailable' WHERE id = %s", (game_id,))
        self._conn.commit()

    def save_window(self, game_id: str, window: WindowResponse) -> None:
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
