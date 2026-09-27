CREATE TABLE IF NOT EXISTS source_registry (
  source_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  publisher TEXT NOT NULL,
  canonical_url TEXT,
  license TEXT,
  frequency TEXT,
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
  default_half_life_days REAL,
  source_id TEXT,
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
);

CREATE TABLE IF NOT EXISTS data_vintage (
  vintage_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  retrieved_at TIMESTAMP NOT NULL,
  source_hash TEXT NOT NULL,
  revision_number INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
);

CREATE TABLE IF NOT EXISTS raw_observation (
  observation_id TEXT PRIMARY KEY,
  feature_id TEXT NOT NULL,
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
  confidence REAL,
  quality_flag TEXT,
  FOREIGN KEY (feature_id) REFERENCES feature_definition(feature_id),
  FOREIGN KEY (vintage_id) REFERENCES data_vintage(vintage_id)
);

CREATE TABLE IF NOT EXISTS feature_dependency (
  parent_feature_id TEXT NOT NULL,
  child_indicator_id INTEGER NOT NULL,
  target_state TEXT NOT NULL,
  attribution_group TEXT NOT NULL,
  PRIMARY KEY(parent_feature_id, child_indicator_id, target_state)
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
  metadata_json TEXT
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
  train_end TIMESTAMP NOT NULL,
  test_start TIMESTAMP NOT NULL,
  test_end TIMESTAMP NOT NULL,
  dataset_hash TEXT NOT NULL,
  code_commit TEXT,
  parameters_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);
