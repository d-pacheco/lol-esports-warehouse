from datetime import datetime, timezone

from psycopg_pool import ConnectionPool

from lol_esports_warehouse.riot.schemas.event_details import Game
from lol_esports_warehouse.riot.schemas.window import WindowResponse
from lol_esports_warehouse.riot.schemas.details import DetailsResponse


class GameDAO:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def update(self, games: list[Game]) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                for g in games:
                    cur.execute("UPDATE games SET state = %s WHERE id = %s", (g.state, g.id))
                    for vod in g.vods:
                        cur.execute(
                            "INSERT INTO vods (game_id, parameter, locale, provider, offset_secs) VALUES (%s, %s, %s, %s, %s) "
                            "ON CONFLICT (game_id, parameter) DO UPDATE SET locale=EXCLUDED.locale, provider=EXCLUDED.provider, offset_secs=EXCLUDED.offset_secs",
                            (g.id, vod.parameter, vod.locale, vod.provider, vod.offset),
                        )
            conn.commit()

    def get_stale_ids(self) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT g.id FROM games g JOIN events e ON g.match_id = e.match_id "
                    "WHERE g.state IN ('unstarted', 'inProgress') AND e.start_time < %s",
                    (now,),
                )
                return [r[0] for r in cur.fetchall()]

    def get_completed_ids_without_frames(self) -> list[str]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT g.id FROM games g LEFT JOIN game_metadata gm ON g.id = gm.game_id "
                    "WHERE g.state = 'completed' AND gm.game_id IS NULL "
                    "AND (g.frames_status IS NULL OR g.frames_status != 'unavailable')"
                )
                return [r[0] for r in cur.fetchall()]

    def mark_frames_unavailable(self, game_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE games SET frames_status = 'unavailable' WHERE id = %s", (game_id,))
            conn.commit()

    def save_window(self, game_id: str, window: WindowResponse) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
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
            conn.commit()

    def get_completed_ids_without_details(self) -> list[str]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM games WHERE state = 'completed' "
                    "AND (details_status IS NULL OR details_status NOT IN ('available', 'unavailable'))"
                )
                return [r[0] for r in cur.fetchall()]

    def mark_details_unavailable(self, game_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE games SET details_status = 'unavailable' WHERE id = %s", (game_id,))
            conn.commit()

    def save_details(self, game_id: str, details: DetailsResponse) -> None:
        perks_saved: set[int] = set()
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE games SET details_status = 'available' WHERE id = %s", (game_id,))
                for frame in details.frames:
                    for p in frame.participants:
                        cur.execute(
                            "INSERT INTO game_participant_frames "
                            "(game_id, participant_id, timestamp, level, kills, deaths, assists, "
                            "creep_score, total_gold, current_health, max_health, total_gold_earned, "
                            "kill_participation, champion_damage_share, wards_placed, wards_destroyed, "
                            "attack_damage, ability_power, critical_chance, attack_speed, life_steal, "
                            "armor, magic_resistance, tenacity, items, abilities) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                            "ON CONFLICT (game_id, participant_id, timestamp) DO UPDATE SET "
                            "level=EXCLUDED.level, kills=EXCLUDED.kills, deaths=EXCLUDED.deaths, "
                            "assists=EXCLUDED.assists, creep_score=EXCLUDED.creep_score, "
                            "total_gold=EXCLUDED.total_gold, current_health=EXCLUDED.current_health, "
                            "max_health=EXCLUDED.max_health, total_gold_earned=EXCLUDED.total_gold_earned, "
                            "kill_participation=EXCLUDED.kill_participation, "
                            "champion_damage_share=EXCLUDED.champion_damage_share, "
                            "wards_placed=EXCLUDED.wards_placed, wards_destroyed=EXCLUDED.wards_destroyed, "
                            "attack_damage=EXCLUDED.attack_damage, ability_power=EXCLUDED.ability_power, "
                            "critical_chance=EXCLUDED.critical_chance, attack_speed=EXCLUDED.attack_speed, "
                            "life_steal=EXCLUDED.life_steal, armor=EXCLUDED.armor, "
                            "magic_resistance=EXCLUDED.magic_resistance, tenacity=EXCLUDED.tenacity, "
                            "items=EXCLUDED.items, abilities=EXCLUDED.abilities",
                            (game_id, p.participantId, frame.rfc460Timestamp,
                             p.level, p.kills, p.deaths, p.assists,
                             p.creepScore, p.totalGold, p.currentHealth, p.maxHealth, p.totalGoldEarned,
                             p.killParticipation, p.championDamageShare, p.wardsPlaced, p.wardsDestroyed,
                             p.attackDamage, p.abilityPower, p.criticalChance, p.attackSpeed, p.lifeSteal,
                             p.armor, p.magicResistance, p.tenacity, p.items, p.abilities),
                        )
                        if p.participantId not in perks_saved:
                            perks_saved.add(p.participantId)
                            cur.execute(
                                "INSERT INTO game_participant_perks "
                                "(game_id, participant_id, style_id, sub_style_id, perks) "
                                "VALUES (%s, %s, %s, %s, %s) "
                                "ON CONFLICT (game_id, participant_id) DO UPDATE SET "
                                "style_id=EXCLUDED.style_id, sub_style_id=EXCLUDED.sub_style_id, perks=EXCLUDED.perks",
                                (game_id, p.participantId,
                                 p.perkMetadata.styleId, p.perkMetadata.subStyleId, p.perkMetadata.perks),
                            )
            conn.commit()
