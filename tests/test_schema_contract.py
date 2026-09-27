import sqlite3
from pathlib import Path

import pytest

SCHEMA = Path(__file__).parents[1] / "sql" / "schema.sql"


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text())
    return connection


def seed_source_and_feature(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO source_registry(source_id, name, publisher)
        VALUES ('treasury', 'Treasury Auctions', 'US Treasury')
        """
    )
    connection.execute(
        """
        INSERT INTO feature_definition(feature_id, indicator_id, name, source_id)
        VALUES ('auction_tail', 3, 'Auction Tail', 'treasury')
        """
    )
    connection.execute(
        """
        INSERT INTO data_vintage(
          vintage_id, source_id, retrieved_at, source_hash, revision_number
        ) VALUES (
          'treasury:0:abc', 'treasury', '2020-01-03T00:00:00+00:00', 'abc', 0
        )
        """
    )


def test_schema_accepts_missing_value_but_not_missing_contract_fields():
    connection = database()
    seed_source_and_feature(connection)

    connection.execute(
        """
        INSERT INTO raw_observation(
          observation_id, feature_id, source_id, value, available_at,
          ingested_at, vintage_id
        ) VALUES (
          'o1', 'auction_tail', 'treasury', NULL,
          '2020-01-02T00:00:00+00:00', '2020-01-03T00:00:00+00:00',
          'treasury:0:abc'
        )
        """
    )
    assert connection.execute(
        "SELECT value FROM raw_observation WHERE observation_id='o1'"
    ).fetchone()[0] is None


def test_schema_rejects_duplicate_state_attribution():
    connection = database()
    seed_source_and_feature(connection)

    connection.execute(
        """
        INSERT INTO feature_dependency(
          parent_feature_id, child_indicator_id, target_state, attribution_group
        ) VALUES ('auction_tail', 3, 'B', 'auction')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO feature_dependency(
              parent_feature_id, child_indicator_id, target_state, attribution_group
            ) VALUES ('auction_tail', 2, 'B', 'repo')
            """
        )
