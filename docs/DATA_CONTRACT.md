# Point-in-time data contract

The core historical invariant is:

```text
available_at <= decision_time
```

`available_at` is the time at which a value could first have been known to a market participant under the source's normal public-access conditions. It is the backtest gate.

## Time fields

- `observation_start / observation_end`: economic period represented by the value.
- `published_at`: source publication timestamp when known.
- `available_at`: first timestamp when the value was actually usable. This must be greater than or equal to `published_at`.
- `ingested_at`: when this project collected the record. It is audit metadata, not a historical-availability gate. Backfilled data may be ingested years later.
- `revised_at`: source-declared timestamp associated with the revision represented by this row, when known. It must not be later than `available_at`.

All timestamps are timezone-aware.

## Revisions

A revised release is stored as a new vintage and a new raw observation. Old values are not overwritten.

For a historical decision time, the snapshot selects the latest eligible version of the same natural observation key:

```text
(feature_id, entity_id, observation_start, observation_end)
```

A future revision therefore cannot leak backward into an earlier test date.

## Missing data

A missing value is represented by `value = null`.

Missing is not zero. Missing observations must not be silently imputed in the raw layer. Any later modeling imputation must be explicit, versioned and testable.

## Source hash and vintage identity

`source_hash` is SHA-256 over the exact raw bytes retrieved from the source.

A deterministic vintage ID is:

```text
{source_id}:{revision_number}:{first_16_hex_chars_of_source_hash}
```

The database additionally enforces uniqueness of `(source_id, source_hash)`.

## Dataset hash

A backtest snapshot hash is SHA-256 over a canonical, sorted serialization of:

- every selected observation;
- the vintage metadata for every selected observation.

The hash is independent of input ordering but changes when an observation value, availability timestamp, revision number or source hash changes.

## Duplicate attribution

A raw feature may be reused across different latent states, but it may not enter the same latent state through multiple first-level indicators. This prevents hidden double counting.

The SQL schema enforces uniqueness of:

```text
(parent_feature_id, target_state)
```

and the Python validation layer applies the same invariant.
