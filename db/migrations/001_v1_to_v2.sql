USE arena_duel_v2_db;

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS status_code VARCHAR(24) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS last_seen_at DATETIME NULL,
    ADD COLUMN IF NOT EXISTS archived_at DATETIME NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS arenas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    label VARCHAR(120) NOT NULL,
    asset_path VARCHAR(255) NOT NULL,
    layout_version VARCHAR(64) NOT NULL DEFAULT '1',
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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
        FOREIGN KEY (arena_id) REFERENCES arenas(id)
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
        FOREIGN KEY (player_id) REFERENCES players(id)
);

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS mode_code VARCHAR(24) NOT NULL DEFAULT 'LEGACY',
    ADD COLUMN IF NOT EXISTS source_code VARCHAR(24) NOT NULL DEFAULT 'LEGACY',
    ADD COLUMN IF NOT EXISTS status_code VARCHAR(24) NOT NULL DEFAULT 'COMPLETED',
    ADD COLUMN IF NOT EXISTS arena_id INT NULL,
    ADD COLUMN IF NOT EXISTS arena_code_snapshot VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS lobby_session_id INT NULL,
    ADD COLUMN IF NOT EXISTS created_by_player_id INT NULL,
    ADD COLUMN IF NOT EXISTS started_at DATETIME NULL,
    ADD COLUMN IF NOT EXISTS finished_at DATETIME NULL,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

UPDATE matches
SET
    arena_code_snapshot = COALESCE(arena_code_snapshot, 'forgotten_sanctum'),
    finished_at = COALESCE(finished_at, played_at),
    mode_code = CASE
        WHEN mode_code IS NULL OR mode_code = '' THEN 'LEGACY'
        ELSE mode_code
    END,
    source_code = CASE
        WHEN source_code IS NULL OR source_code = '' THEN 'LEGACY'
        ELSE source_code
    END,
    status_code = CASE
        WHEN status_code IS NULL OR status_code = '' THEN 'COMPLETED'
        ELSE status_code
    END;

ALTER TABLE match_players
    MODIFY COLUMN player_id INT NULL,
    ADD COLUMN IF NOT EXISTS display_name_snapshot VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS slot_number INT NULL,
    ADD COLUMN IF NOT EXISTS control_mode VARCHAR(24) NULL,
    ADD COLUMN IF NOT EXISTS is_ai TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ai_difficulty_code VARCHAR(24) NULL,
    ADD COLUMN IF NOT EXISTS ai_profile_code VARCHAR(24) NULL,
    ADD COLUMN IF NOT EXISTS ready_at_start TINYINT(1) NULL,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

UPDATE match_players mp
JOIN players p ON p.id = mp.player_id
SET
    mp.display_name_snapshot = COALESCE(mp.display_name_snapshot, p.username),
    mp.control_mode = COALESCE(mp.control_mode, 'human'),
    mp.is_ai = CASE
        WHEN p.username LIKE '[IA] %' THEN 1
        ELSE mp.is_ai
    END;

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