SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    source_doc TEXT NOT NULL,
    response TEXT,
    model_name TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error TEXT,
    batch_id INTEGER,
    row_index INTEGER
);

CREATE INDEX IF NOT EXISTS idx_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch ON processing_jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_filename ON processing_jobs(filename);
"""

def get_schema_sql():
    return SCHEMA_SQL 