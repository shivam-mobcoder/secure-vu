-- POC: alert history and continuous recording segment index

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
    person TEXT NOT NULL,
    event TEXT NOT NULL,
    priority SMALLINT,
    clip_url TEXT,
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recording_segments (
    id BIGSERIAL PRIMARY KEY,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ,
    size_bytes BIGINT
);

CREATE INDEX IF NOT EXISTS alerts_created_idx ON alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS alerts_client_created_idx ON alerts (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS recordings_camera_idx ON recording_segments (camera_id, start_ts DESC);
