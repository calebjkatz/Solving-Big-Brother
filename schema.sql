CREATE TABLE IF NOT EXISTS franchises (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    edition TEXT NOT NULL DEFAULT 'civilian'
);

CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY,
    franchise_id INTEGER NOT NULL REFERENCES franchises(id),
    season_number INTEGER NOT NULL,
    title TEXT,
    year INTEGER,
    notes TEXT,
    UNIQUE(franchise_id, season_number)
);

CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    aliases TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    skills TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT '',
    strategy_evidence TEXT NOT NULL DEFAULT '',
    image_url TEXT NOT NULL DEFAULT '',
    image_source TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'needs verification',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competition_instances (
    id INTEGER PRIMARY KEY,
    competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    week TEXT NOT NULL DEFAULT '',
    day TEXT NOT NULL DEFAULT '',
    source_event_key TEXT NOT NULL DEFAULT '',
    episode INTEGER,
    air_date TEXT,
    competition_type TEXT NOT NULL DEFAULT '',
    variation_name TEXT NOT NULL DEFAULT '',
    rules_notes TEXT NOT NULL DEFAULT '',
    strategy_notes TEXT NOT NULL DEFAULT '',
    image_url TEXT NOT NULL DEFAULT '',
    video_url TEXT NOT NULL DEFAULT '',
    guest_appearances TEXT NOT NULL DEFAULT '',
    workbook_family TEXT NOT NULL DEFAULT '',
    workbook_sheet TEXT NOT NULL DEFAULT '',
    workbook_row INTEGER,
    winner TEXT NOT NULL DEFAULT '',
    outcome_notes TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'needs verification',
    UNIQUE(competition_id, season_id, episode, variation_name)
);

CREATE TABLE IF NOT EXISTS houseguests (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '',
    strengths TEXT NOT NULL DEFAULT '',
    weaknesses TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    image_url TEXT NOT NULL DEFAULT '',
    image_source TEXT NOT NULL DEFAULT '',
    person_key TEXT NOT NULL DEFAULT '',
    profile_url TEXT NOT NULL DEFAULT '',
    UNIQUE(season_id, name)
);

CREATE TABLE IF NOT EXISTS competition_participants (
    id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES competition_instances(id) ON DELETE CASCADE,
    houseguest_id INTEGER NOT NULL REFERENCES houseguests(id) ON DELETE CASCADE,
    placement INTEGER,
    score TEXT,
    eliminated_order INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(instance_id, houseguest_id)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
    instance_id INTEGER REFERENCES competition_instances(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'secondary',
    accessed_on TEXT,
    notes TEXT NOT NULL DEFAULT '',
    CHECK (competition_id IS NOT NULL OR instance_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_instances_competition ON competition_instances(competition_id);
CREATE INDEX IF NOT EXISTS idx_instances_season ON competition_instances(season_id);
