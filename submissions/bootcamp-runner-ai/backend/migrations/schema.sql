CREATE TABLE player_profiles (
    player_id VARCHAR(128) NOT NULL PRIMARY KEY,
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(320) NOT NULL UNIQUE,
    strengths VARCHAR(4000), growth_areas VARCHAR(4000),
    preferred_difficulty VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (preferred_difficulty IN ('easy','medium','hard')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE TABLE game_sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    mode VARCHAR(80) NOT NULL, difficulty VARCHAR(10) NOT NULL
        CHECK (difficulty IN ('easy','medium','hard')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE TABLE game_scores (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES game_sessions(id),
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    score DECIMAL(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    points INTEGER NOT NULL CHECK (points >= 0),
    rounds_completed INTEGER NOT NULL CHECK (rounds_completed >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE INDEX idx_game_scores_player ON game_scores(player_id, created_at);
CREATE TABLE character_unlocks (
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    character_key VARCHAR(80) NOT NULL, unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (player_id, character_key)
);
CREATE TABLE achievements (
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    achievement_key VARCHAR(80) NOT NULL, title VARCHAR(200) NOT NULL,
    description VARCHAR(1000), unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (player_id, achievement_key)
);
CREATE TABLE player_missions (
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    mission_key VARCHAR(80) NOT NULL, title VARCHAR(200) NOT NULL,
    description VARCHAR(1000), status VARCHAR(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available','active','completed')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (player_id, mission_key)
);
CREATE TABLE assistant_challenges (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id VARCHAR(128) NOT NULL REFERENCES player_profiles(player_id),
    objective VARCHAR(2000) NOT NULL, challenge VARCHAR(4000) NOT NULL,
    difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    source VARCHAR(40) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
