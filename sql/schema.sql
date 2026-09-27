PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_registry (
  source_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  publisher TEXT NOT NULL,
  canonical_url TEXT,
  license TEXT,
  frequency TEXT,
  typical_publication_lag_hours REAL CHECK (
    typical_publication_lag_hours IS NULL OR typical_publication_lag_hours >= 0
  ),
  revision_policy TEXT,
  point_in_time_capable BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS feature_definition (
  feature_id TEXT PRIMARY KEY,
  indicator_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  unit TEXT,
  transform TEXT,
  expected_frequency TEXT,
  default_half_life_days REAL CHECK (
    default_half_life_days IS NULL OR default_half_life_days > 0
  ),
  source_id TEXT,
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
);

CREATE TABLE IF NOT EXISTS data_vintage (
  vintage_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  retrieved_at TIMESTAMP NOT NULL,
  source_hash TEXT NOT NULL,
  revision_number INTEGER NOT NULL DEFAULT 0 CHECK (revision_number >= 0),
  UNIQUE(source_id, source_hash),
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
);

CREATE TABLE IF NOT EXISTS raw_observation (
  observation_id TEXT PRIMARY KEY,
  feature_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  entity_id TEXT,
  value REAL,
  unit TEXT,
  observation_start TIMESTAMP,
  observation_end TIMESTAMP,
  published_at TIMESTAMP,
  available_at TIMESTAMP NOT NULL,
  ingested_at TIMESTAMP NOT NULL,
  revised_at TIMESTAMP,
  vintage_id TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
  quality_flag TEXT,
  CHECK (observation_end IS NULL OR observation_start IS NULL OR observation_end >= observation_start),
  CHECK (published_at IS NULL OR available_at >= published_at),
  CHECK (ingested_at >= available_at),
  CHECK (revised_at IS NULL OR revised_at <= available_at),
  FOREIGN KEY (feature_id) REFERENCES feature_definition(feature_id),
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id),
  FOREIGN KEY (vintage_id) REFERENCES data_vintage(vintage_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_observation_point_in_time
ON raw_observation(feature_id, entity_id, observation_start, observation_end, available_at);

CREATE TABLE IF NOT EXISTS feature_dependency (
  parent_feature_id TEXT NOT NULL,
  child_indicator_id INTEGER NOT NULL,
  target_state TEXT NOT NULL,
  attribution_group TEXT NOT NULL,
  PRIMARY KEY(parent_feature_id, child_indicator_id, target_state),
  UNIQUE(parent_feature_id, target_state),
  FOREIGN KEY (parent_feature_id) REFERENCES feature_definition(feature_id)
);

CREATE TABLE IF NOT EXISTS event_registry (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  country TEXT,
  announcement_at TIMESTAMP NOT NULL,
  effective_at TIMESTAMP,
  magnitude REAL,
  source_id TEXT,
  status TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
);

CREATE TABLE IF NOT EXISTS normalized_signal (
  run_id TEXT NOT NULL,
  feature_id TEXT NOT NULL,
  as_of TIMESTAMP NOT NULL,
  z_score REAL,
  freshness REAL,
  confidence REAL,
  measurement_variance REAL,
  is_missing BOOLEAN NOT NULL,
  PRIMARY KEY(run_id, feature_id, as_of)
);

CREATE TABLE IF NOT EXISTS latent_state (
  run_id TEXT NOT NULL,
  as_of TIMESTAMP NOT NULL,
  state_key TEXT NOT NULL,
  state_value REAL NOT NULL,
  variance REAL,
  ci_low REAL,
  ci_high REAL,
  confidence TEXT,
  model_version TEXT NOT NULL,
  PRIMARY KEY(run_id, as_of, state_key)
);

CREATE TABLE IF NOT EXISTS stress_state (
  run_id TEXT NOT NULL,
  as_of TIMESTAMP NOT NULL,
  funding REAL,
  price_discovery REAL,
  intermediation REAL,
  stress_level TEXT NOT NULL,
  PRIMARY KEY(run_id, as_of)
);

CREATE TABLE IF NOT EXISTS backtest_run (
  run_id TEXT PRIMARY KEY,
  model_version TEXT NOT NULL,
  feature_set_version TEXT NOT NULL,
  fold_id TEXT NOT NULL,
  universe TEXT NOT NULL,
  train_end TIMESTAMP NOT NULL,
  test_start TIMESTAMP NOT NULL,
  test_end TIMESTAMP NOT NULL,
  dataset_hash TEXT NOT NULL,
  code_commit TEXT NOT NULL,
  parameters_json TEXT NOT NULL,
  parameters_hash TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);


CREATE TABLE IF NOT EXISTS daily_snapshot (
  snapshot_id TEXT PRIMARY KEY,
  as_of TIMESTAMP NOT NULL,
  model_version TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL UNIQUE,
  stress_level TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  markdown TEXT NOT NULL,
  generated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_snapshot_as_of
ON daily_snapshot(as_of, model_version);


CREATE TABLE IF NOT EXISTS arbitration_report (
  report_id TEXT PRIMARY KEY,
  as_of TIMESTAMP NOT NULL,
  snapshot_hash TEXT NOT NULL,
  trigger_reasons_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS arbitration_claim_decision (
  report_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  role TEXT NOT NULL,
  topic TEXT NOT NULL,
  original_kind TEXT NOT NULL,
  final_kind TEXT NOT NULL,
  disposition TEXT NOT NULL,
  reason TEXT NOT NULL,
  missing_sources_json TEXT NOT NULL,
  PRIMARY KEY(report_id, claim_id),
  FOREIGN KEY (report_id) REFERENCES arbitration_report(report_id)
);


CREATE TABLE IF NOT EXISTS shadow_run (
  run_id TEXT PRIMARY KEY,
  decision_time TIMESTAMP NOT NULL,
  generated_at TIMESTAMP NOT NULL,
  status TEXT NOT NULL,
  dataset_hash TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  feature_set_version TEXT NOT NULL,
  missing_requirements_json TEXT NOT NULL,
  disagreement_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shadow_engine_state (
  run_id TEXT NOT NULL,
  engine TEXT NOT NULL,
  state_key TEXT NOT NULL,
  state_value REAL NOT NULL,
  variance REAL,
  confidence TEXT,
  PRIMARY KEY(run_id, engine, state_key),
  FOREIGN KEY (run_id) REFERENCES shadow_run(run_id)
);

CREATE TABLE IF NOT EXISTS shadow_outcome (
  run_id TEXT NOT NULL,
  horizon_days INTEGER NOT NULL,
  attached_at TIMESTAMP NOT NULL,
  outcome_json TEXT NOT NULL,
  PRIMARY KEY(run_id, horizon_days),
  FOREIGN KEY (run_id) REFERENCES shadow_run(run_id)
);
