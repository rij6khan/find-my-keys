PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS object_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    timestamp TEXT NOT NULL,
    quest_x REAL NOT NULL,
    quest_y REAL NOT NULL,
    quest_z REAL NOT NULL,
    yor_world_x REAL,
    yor_world_y REAL,
    yor_world_z REAL,
    full_image_path TEXT,
    crop_image_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    observation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (observation_id)
        REFERENCES object_observations (observation_id)
);
