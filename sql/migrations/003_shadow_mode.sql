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
