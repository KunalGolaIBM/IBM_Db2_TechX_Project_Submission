CREATE TABLE player_profiles (
    player_id VARCHAR(128) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(320) NOT NULL,
    strengths VARCHAR(4000),
    growth_areas VARCHAR(4000),
    preferred_difficulty VARCHAR(10) NOT NULL DEFAULT 'medium',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_player_profiles PRIMARY KEY (player_id),
    CONSTRAINT uq_player_profiles_email UNIQUE (email),
    CONSTRAINT ck_player_profiles_difficulty
        CHECK (preferred_difficulty IN ('easy', 'medium', 'hard'))
);

CREATE TABLE game_sessions (
    id BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    player_id VARCHAR(128) NOT NULL,
    mode VARCHAR(80) NOT NULL,
    difficulty VARCHAR(10) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_game_sessions PRIMARY KEY (id),
    CONSTRAINT uq_game_sessions_id_player UNIQUE (id, player_id),
    CONSTRAINT fk_game_sessions_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id),
    CONSTRAINT ck_game_sessions_difficulty
        CHECK (difficulty IN ('easy', 'medium', 'hard'))
);

CREATE TABLE game_scores (
    id BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    session_id BIGINT NOT NULL,
    player_id VARCHAR(128) NOT NULL,
    score BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_game_scores PRIMARY KEY (id),
    CONSTRAINT fk_game_scores_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id),
    CONSTRAINT fk_game_scores_session_player
        FOREIGN KEY (session_id, player_id)
        REFERENCES game_sessions (id, player_id),
    CONSTRAINT ck_game_scores_nonnegative
        CHECK (score >= 0)
);

CREATE INDEX idx_game_scores_player
    ON game_scores (player_id, created_at);

CREATE TABLE character_unlocks (
    player_id VARCHAR(128) NOT NULL,
    character_key VARCHAR(80) NOT NULL,
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_character_unlocks
        PRIMARY KEY (player_id, character_key),
    CONSTRAINT fk_character_unlocks_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id)
);

CREATE TABLE achievements (
    player_id VARCHAR(128) NOT NULL,
    achievement_key VARCHAR(80) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_achievements
        PRIMARY KEY (player_id, achievement_key),
    CONSTRAINT fk_achievements_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id)
);

CREATE TABLE player_missions (
    player_id VARCHAR(128) NOT NULL,
    mission_key VARCHAR(80) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    status VARCHAR(20) NOT NULL DEFAULT 'available',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_player_missions
        PRIMARY KEY (player_id, mission_key),
    CONSTRAINT fk_player_missions_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id),
    CONSTRAINT ck_player_missions_status
        CHECK (status IN ('available', 'active', 'completed'))
);

CREATE TABLE assistant_challenges (
    id BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    player_id VARCHAR(128) NOT NULL,
    objective VARCHAR(2000) NOT NULL,
    challenge VARCHAR(4000) NOT NULL,
    difficulty VARCHAR(10) NOT NULL,
    source VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_assistant_challenges PRIMARY KEY (id),
    CONSTRAINT fk_assistant_challenges_player
        FOREIGN KEY (player_id)
        REFERENCES player_profiles (player_id),
    CONSTRAINT ck_assistant_challenges_difficulty
        CHECK (difficulty IN ('easy', 'medium', 'hard'))
);
