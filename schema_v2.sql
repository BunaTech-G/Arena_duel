-- Bootstrap SQL canonique V2 pour une base neuve Arena Duel.
-- Le fichier shema.sql est conserve comme alias legacy de compatibilite.

CREATE DATABASE IF NOT EXISTS arena_duel_v2_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE arena_duel_v2_db;

CREATE TABLE IF NOT EXISTS players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    status_code VARCHAR(24) NOT NULL DEFAULT 'ACTIVE',
    last_seen_at DATETIME NULL,
    archived_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_players_status (status_code)
);

CREATE TABLE IF NOT EXISTS arenas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    label VARCHAR(120) NOT NULL,
    asset_path VARCHAR(255) NOT NULL,
    layout_version VARCHAR(64) NOT NULL DEFAULT '1',
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_arenas_active (active)
);

INSERT INTO arenas (
    code,
    label,
    asset_path,
    layout_version,
    active
)
VALUES (
    'forgotten_sanctum',
    'Forgotten Sanctum',
    'assets/maps/forgotten_sanctum/layout.json',
    '1',
    1
)
ON DUPLICATE KEY UPDATE
    label = VALUES(label),
    asset_path = VALUES(asset_path),
    layout_version = VALUES(layout_version),
    active = VALUES(active);

CREATE TABLE IF NOT EXISTS player_preferences (
    player_id INT NOT NULL PRIMARY KEY,
    preferred_team_code CHAR(1) NULL,
    preferred_slot INT NULL,
    last_local_mode VARCHAR(24) NULL,
    last_match_duration_seconds INT NULL,
    last_arena_id INT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_player_preferences_player
        FOREIGN KEY (player_id) REFERENCES players(id),
    CONSTRAINT fk_player_preferences_arena
        FOREIGN KEY (last_arena_id) REFERENCES arenas(id)
);

CREATE TABLE IF NOT EXISTS lobby_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invite_code VARCHAR(32) NOT NULL UNIQUE,
    host_player_id INT NULL,
    host_display_name_snapshot VARCHAR(50) NULL,
    arena_id INT NULL,
    match_duration_seconds INT NOT NULL DEFAULT 60,
    source_code VARCHAR(24) NOT NULL DEFAULT 'LAN',
    status_code VARCHAR(24) NOT NULL DEFAULT 'OPEN',
    opened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    closed_at DATETIME NULL,
    CONSTRAINT fk_lobby_sessions_host
        FOREIGN KEY (host_player_id) REFERENCES players(id),
    CONSTRAINT fk_lobby_sessions_arena
        FOREIGN KEY (arena_id) REFERENCES arenas(id),
    KEY idx_lobby_sessions_status (status_code),
    KEY idx_lobby_sessions_opened_at (opened_at)
);

CREATE TABLE IF NOT EXISTS lobby_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lobby_session_id INT NOT NULL,
    player_id INT NULL,
    display_name_snapshot VARCHAR(50) NOT NULL,
    client_id_snapshot VARCHAR(40) NULL,
    slot_number INT NULL,
    team_code CHAR(1) NULL,
    ready_flag TINYINT(1) NOT NULL DEFAULT 0,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at DATETIME NULL,
    CONSTRAINT fk_lobby_members_session
        FOREIGN KEY (lobby_session_id) REFERENCES lobby_sessions(id),
    CONSTRAINT fk_lobby_members_player
        FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE KEY uq_lobby_members_slot (lobby_session_id, slot_number),
    KEY idx_lobby_members_player (player_id),
    KEY idx_lobby_members_ready (ready_flag)
);

CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mode_code VARCHAR(24) NOT NULL DEFAULT 'LOCAL_HUMAN',
    source_code VARCHAR(24) NOT NULL DEFAULT 'LOCAL',
    status_code VARCHAR(24) NOT NULL DEFAULT 'COMPLETED',
    arena_id INT NULL,
    arena_code_snapshot VARCHAR(64) NULL,
    lobby_session_id INT NULL,
    created_by_player_id INT NULL,
    team_a_score INT NOT NULL DEFAULT 0,
    team_b_score INT NOT NULL DEFAULT 0,
    winner_team CHAR(1) NULL,
    duration_seconds INT NOT NULL DEFAULT 60,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    played_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_matches_arena
        FOREIGN KEY (arena_id) REFERENCES arenas(id),
    CONSTRAINT fk_matches_lobby_session
        FOREIGN KEY (lobby_session_id) REFERENCES lobby_sessions(id),
    CONSTRAINT fk_matches_created_by_player
        FOREIGN KEY (created_by_player_id) REFERENCES players(id),
    KEY idx_matches_played_at (played_at),
    KEY idx_matches_mode (mode_code),
    KEY idx_matches_source (source_code),
    KEY idx_matches_status (status_code),
    KEY idx_matches_arena (arena_id),
    KEY idx_matches_lobby_session (lobby_session_id)
);

CREATE TABLE IF NOT EXISTS match_players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT NOT NULL,
    player_id INT NULL,
    display_name_snapshot VARCHAR(50) NOT NULL,
    team_code CHAR(1) NOT NULL,
    slot_number INT NULL,
    control_mode VARCHAR(24) NULL,
    is_ai TINYINT(1) NOT NULL DEFAULT 0,
    ai_difficulty_code VARCHAR(24) NULL,
    ai_profile_code VARCHAR(24) NULL,
    ready_at_start TINYINT(1) NULL,
    individual_score INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_match_players_match
        FOREIGN KEY (match_id) REFERENCES matches(id),
    CONSTRAINT fk_match_players_player
        FOREIGN KEY (player_id) REFERENCES players(id),
    KEY idx_match_players_match (match_id),
    KEY idx_match_players_player (player_id),
    KEY idx_match_players_team (team_code),
    KEY idx_match_players_slot (slot_number),
    KEY idx_match_players_ai (is_ai)
);

DROP VIEW IF EXISTS v_match_history_cards;

CREATE VIEW v_match_history_cards AS
SELECT
    m.id AS match_id,
    COALESCE(a.code, m.arena_code_snapshot, 'unknown') AS arena_code,
    COALESCE(a.label, m.arena_code_snapshot, 'Arena inconnue') AS arena_label,
    m.mode_code,
    m.source_code,
    m.status_code,
    GROUP_CONCAT(
        CASE WHEN mp.team_code = 'A' THEN mp.display_name_snapshot END
        ORDER BY COALESCE(mp.slot_number, 999), mp.id
        SEPARATOR ', '
    ) AS team_a_players,
    GROUP_CONCAT(
        CASE WHEN mp.team_code = 'B' THEN mp.display_name_snapshot END
        ORDER BY COALESCE(mp.slot_number, 999), mp.id
        SEPARATOR ', '
    ) AS team_b_players,
    m.team_a_score,
    m.team_b_score,
    m.winner_team,
    m.duration_seconds,
    m.played_at,
    SUM(CASE WHEN mp.is_ai = 1 THEN 1 ELSE 0 END) AS ai_participants
FROM matches m
LEFT JOIN arenas a
    ON a.id = m.arena_id
LEFT JOIN match_players mp
    ON mp.match_id = m.id
GROUP BY
    m.id,
    a.code,
    a.label,
    m.arena_code_snapshot,
    m.mode_code,
    m.source_code,
    m.status_code,
    m.team_a_score,
    m.team_b_score,
    m.winner_team,
    m.duration_seconds,
    m.played_at;

DROP VIEW IF EXISTS v_player_career_stats;

CREATE VIEW v_player_career_stats AS
SELECT
    p.id AS player_id,
    p.username,
    COUNT(DISTINCT CASE WHEN m.id IS NOT NULL THEN mp.match_id END) AS matches_played,
    SUM(CASE WHEN m.winner_team = mp.team_code THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN m.winner_team IS NULL THEN 1 ELSE 0 END) AS draws,
    SUM(
        CASE
            WHEN m.winner_team IS NOT NULL AND m.winner_team <> mp.team_code
                THEN 1
            ELSE 0
        END
    ) AS losses,
    COALESCE(SUM(mp.individual_score), 0) AS total_individual_score,
    ROUND(AVG(mp.individual_score), 2) AS average_individual_score,
    MAX(m.played_at) AS last_played_at
FROM players p
LEFT JOIN match_players mp
    ON mp.player_id = p.id
LEFT JOIN matches m
    ON m.id = mp.match_id
    AND m.status_code = 'COMPLETED'
GROUP BY
    p.id,
    p.username;

DROP VIEW IF EXISTS v_team_career_stats;

CREATE VIEW v_team_career_stats AS
SELECT
    team_rollup.team_code,
    COUNT(*) AS matches_played,
    SUM(CASE WHEN team_rollup.winner_team = team_rollup.team_code THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN team_rollup.winner_team IS NULL THEN 1 ELSE 0 END) AS draws,
    SUM(
        CASE
            WHEN team_rollup.winner_team IS NOT NULL
                 AND team_rollup.winner_team <> team_rollup.team_code
                THEN 1
            ELSE 0
        END
    ) AS losses,
    SUM(team_rollup.team_score) AS total_points_scored
FROM (
    SELECT
        'A' AS team_code,
        m.winner_team,
        m.team_a_score AS team_score
    FROM matches m
    WHERE m.status_code = 'COMPLETED'

    UNION ALL

    SELECT
        'B' AS team_code,
        m.winner_team,
        m.team_b_score AS team_score
    FROM matches m
    WHERE m.status_code = 'COMPLETED'
) AS team_rollup
GROUP BY team_rollup.team_code;