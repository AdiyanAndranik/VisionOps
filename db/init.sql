CREATE TABLE runs (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'done', 'failed')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    fps         REAL NOT NULL,
    width       INT,
    height      INT,
    frame_count INT,
    config      JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE events (
    id        BIGSERIAL PRIMARY KEY,
    run_id    BIGINT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    type      TEXT NOT NULL CHECK (type IN ('line_cross', 'zone_enter', 'zone_exit')),
    track_id  INT NOT NULL,
    time_s    DOUBLE PRECISION NOT NULL,
    frame     INT NOT NULL,
    zone      TEXT,
    line      TEXT,
    direction TEXT,
    x         REAL,
    y         REAL,
    start_s   DOUBLE PRECISION,
    dwell_s   DOUBLE PRECISION,
    CHECK (
        (type = 'line_cross' AND line IS NOT NULL AND direction IS NOT NULL AND zone IS NULL)
        OR
        (type IN ('zone_enter', 'zone_exit') AND zone IS NOT NULL AND start_s IS NOT NULL AND line IS NULL)
    )
);

CREATE INDEX events_run_time ON events (run_id, time_s);
CREATE INDEX events_run_type ON events (run_id, type);

-- live feed: the api listens on this channel and pushes to websockets
CREATE FUNCTION notify_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('visionops_events', json_build_object(
        'kind', 'event', 'run_id', NEW.run_id, 'event', row_to_json(NEW))::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_notify AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION notify_event();

CREATE FUNCTION notify_run_done() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('visionops_events', json_build_object(
        'kind', 'run_done', 'run_id', NEW.id, 'status', NEW.status)::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER runs_notify_done AFTER UPDATE OF status ON runs
    FOR EACH ROW
    WHEN (NEW.status IN ('done', 'failed') AND OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION notify_run_done();