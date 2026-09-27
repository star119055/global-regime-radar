CREATE TABLE IF NOT EXISTS opportunity_assessment (
  assessment_id TEXT PRIMARY KEY,
  as_of TIMESTAMP NOT NULL,
  asset_id TEXT NOT NULL,
  opportunity_class TEXT NOT NULL,
  status TEXT NOT NULL,
  score REAL,
  gate_ratio REAL NOT NULL,
  impairment_score REAL NOT NULL,
  regime_engine TEXT NOT NULL,
  model_version TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_gate (
  assessment_id TEXT NOT NULL,
  gate_name TEXT NOT NULL,
  passed BOOLEAN NOT NULL,
  actual TEXT NOT NULL,
  threshold TEXT NOT NULL,
  detail TEXT NOT NULL,
  PRIMARY KEY(assessment_id, gate_name),
  FOREIGN KEY (assessment_id) REFERENCES opportunity_assessment(assessment_id)
);
