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
