-- Schema of v0.1.0 (PRAGMA user_version 0), kept to test the migration to version 2.
CREATE TABLE IF NOT EXISTS job (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    track TEXT,
    score REAL,
    status TEXT NOT NULL,
    next_step TEXT,
    applied_on TEXT,
    last_contact_on TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    relationship TEXT,
    channel TEXT,
    status TEXT NOT NULL,
    next_step TEXT,
    last_contact_on TEXT,
    job_id INTEGER REFERENCES job (id)
);

CREATE TABLE IF NOT EXISTS interaction (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact (id),
    date TEXT NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_history (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job (id),
    date TEXT NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL
);
