-- terminal-insight-v2 facts schema v1
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version     INTEGER PRIMARY KEY,
  applied_at  TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
  device_id   TEXT PRIMARY KEY,
  category    TEXT NOT NULL,
  brand       TEXT NOT NULL,
  brand_norm  TEXT NOT NULL,
  model       TEXT NOT NULL,
  model_norm  TEXT NOT NULL,
  region      TEXT NOT NULL DEFAULT 'CN',
  release_date TEXT,
  status      TEXT NOT NULL DEFAULT 'pending',
  schema_id   TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_devices_lookup
  ON devices(category, brand_norm, model_norm);
CREATE INDEX IF NOT EXISTS idx_devices_status
  ON devices(status);

CREATE TABLE IF NOT EXISTS sources (
  source_id     TEXT PRIMARY KEY,
  url           TEXT NOT NULL,
  url_norm      TEXT NOT NULL UNIQUE,
  host          TEXT,
  tier          TEXT,
  source_kind   TEXT,
  global_status TEXT NOT NULL DEFAULT 'active',
  first_seen    TEXT NOT NULL,
  last_fetch    TEXT
);

CREATE TABLE IF NOT EXISTS device_sources (
  device_id       TEXT NOT NULL,
  source_id       TEXT NOT NULL,
  link_role       TEXT NOT NULL,
  identity_status TEXT NOT NULL DEFAULT 'unknown',
  review_status   TEXT NOT NULL DEFAULT 'auto',
  discovered_by   TEXT,
  not_available   INTEGER NOT NULL DEFAULT 0,
  batch_id        TEXT,
  PRIMARY KEY (device_id, source_id, link_role),
  FOREIGN KEY (device_id) REFERENCES devices(device_id),
  FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_device_sources_device
  ON device_sources(device_id, review_status);

CREATE TABLE IF NOT EXISTS blobs (
  blob_id      TEXT PRIMARY KEY,
  sha256       TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL,
  byte_size    INTEGER NOT NULL,
  rel_path     TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id      TEXT PRIMARY KEY,
  source_id        TEXT NOT NULL,
  device_id        TEXT,
  fetched_at       TEXT NOT NULL,
  fetch_method     TEXT NOT NULL,
  http_status      INTEGER,
  final_url        TEXT,
  raw_status       TEXT NOT NULL,
  raw_html_blob    TEXT,
  raw_json_blob    TEXT,
  content_md_blob  TEXT,
  content_json_blob TEXT,
  content_sha256   TEXT,
  converter_version TEXT,
  error            TEXT,
  match_ok         INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (source_id) REFERENCES sources(source_id),
  FOREIGN KEY (device_id) REFERENCES devices(device_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_source
  ON snapshots(source_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_device
  ON snapshots(device_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS field_assertions (
  assertion_id   TEXT PRIMARY KEY,
  device_id      TEXT NOT NULL,
  field_name     TEXT NOT NULL,
  value_text     TEXT NOT NULL,
  value_norm     TEXT,
  snapshot_id    TEXT NOT NULL,
  source_id      TEXT NOT NULL,
  snippet        TEXT NOT NULL,
  extract_method TEXT NOT NULL,
  confidence     REAL,
  run_id         TEXT NOT NULL,
  created_at     TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES devices(device_id),
  FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
  FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_assertions_device_field
  ON field_assertions(device_id, field_name);

CREATE TABLE IF NOT EXISTS verifications (
  verification_id TEXT PRIMARY KEY,
  assertion_id    TEXT NOT NULL,
  identity_ok     INTEGER NOT NULL,
  evidence_ok     INTEGER NOT NULL,
  accuracy_status TEXT NOT NULL,
  notes           TEXT,
  checked_at      TEXT NOT NULL,
  checker         TEXT NOT NULL,
  FOREIGN KEY (assertion_id) REFERENCES field_assertions(assertion_id)
);

CREATE TABLE IF NOT EXISTS resolutions (
  device_id              TEXT NOT NULL,
  field_name             TEXT NOT NULL,
  display_text           TEXT NOT NULL,
  policy                 TEXT NOT NULL,
  selected_assertion_ids TEXT NOT NULL,
  conflict               INTEGER NOT NULL DEFAULT 0,
  locked                 INTEGER NOT NULL DEFAULT 0,
  locked_value           TEXT,
  resolved_at            TEXT NOT NULL,
  run_id                 TEXT NOT NULL,
  PRIMARY KEY (device_id, field_name, run_id),
  FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE TABLE IF NOT EXISTS review_decisions (
  decision_id TEXT PRIMARY KEY,
  scope       TEXT NOT NULL,
  device_id   TEXT,
  source_id   TEXT,
  field_name  TEXT,
  action      TEXT NOT NULL,
  value_text  TEXT,
  note        TEXT,
  actor       TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_decisions_device
  ON review_decisions(device_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id             TEXT PRIMARY KEY,
  category           TEXT NOT NULL,
  schema_fingerprint TEXT NOT NULL,
  date_start         TEXT,
  date_end           TEXT,
  status             TEXT NOT NULL,
  backfill_round     INTEGER NOT NULL DEFAULT 0,
  input_revision     TEXT NOT NULL,
  rel_path           TEXT,
  created_at         TEXT NOT NULL,
  finished_at        TEXT
);

CREATE TABLE IF NOT EXISTS stage_runs (
  stage_run_id    TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  stage           TEXT NOT NULL,
  status          TEXT NOT NULL,
  attempt         INTEGER NOT NULL DEFAULT 1,
  input_revision  TEXT NOT NULL,
  output_revision TEXT,
  error           TEXT,
  started_at      TEXT,
  finished_at     TEXT,
  UNIQUE (run_id, stage, attempt),
  FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_stage_runs_run
  ON stage_runs(run_id, stage);

CREATE TABLE IF NOT EXISTS category_schemas (
  schema_id      TEXT PRIMARY KEY,
  category       TEXT NOT NULL,
  version        TEXT NOT NULL,
  fingerprint    TEXT NOT NULL UNIQUE,
  template_path  TEXT NOT NULL,
  compiled_json  TEXT NOT NULL,
  compiled_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_category_schemas_cat
  ON category_schemas(category, compiled_at DESC);
