SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    image TEXT NOT NULL,
    region TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tournaments (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    league_id TEXT NOT NULL REFERENCES leagues(id)
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
CREATE TABLE IF NOT EXISTS events (
    match_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    block_name TEXT NOT NULL,
    state TEXT NOT NULL,
    league_id TEXT REFERENCES leagues(id),
    tournament_id TEXT REFERENCES tournaments(id),
    strategy_type TEXT NOT NULL,
    strategy_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS event_teams (
    match_id TEXT NOT NULL REFERENCES events(match_id),
    team_id TEXT REFERENCES teams(id),
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
    team_id TEXT NOT NULL REFERENCES teams(id),
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
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    patch_version TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS game_participant_metadata (
    game_id TEXT NOT NULL REFERENCES games(id),
    participant_id INTEGER NOT NULL,
    esports_team_id TEXT NOT NULL DEFAULT '',
    team_side TEXT NOT NULL,
    summoner_name TEXT NOT NULL DEFAULT '',
    champion_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (game_id, participant_id)
);
CREATE TABLE IF NOT EXISTS game_team_frames (
    game_id TEXT NOT NULL REFERENCES games(id),
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
    game_id TEXT NOT NULL REFERENCES games(id),
    dragon_number INTEGER NOT NULL,
    team_side TEXT NOT NULL,
    dragon_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    PRIMARY KEY (game_id, dragon_number)
);
"""
