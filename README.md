# Global Regime Radar

An open, auditable implementation of the **V6.1 Global Regime & Fat-Pitch Opportunity Radar**.

The project is designed as a point-in-time macro research system rather than a market-prediction engine. It continuously estimates six interacting regime states:

- **A** — AI productivity realization
- **B** — financial microstructure deleveraging
- **C1** — core-economy stagflation
- **C2** — peripheral sovereign stress
- **C3** — industrial-capital-goods inflation
- **D** — financial repression

The implementation deliberately separates:

1. exogenous shocks,
2. spatial/time-lag routing,
3. latent regime states,
4. market-function stress,
5. asset mispricing / fat-pitch detection,
6. permanent-impairment filtering.

## Current scope

V6.1 is frozen at the theory level. The repository now focuses on reproducible data engineering and walk-forward validation.

The first implementation milestones are:

- point-in-time data contracts and vintages;
- Treasury / repo / dealer / auction stress data;
- Stress Engine V0;
- macro and physical-delivery data;
- walk-forward backtesting with publication lags and revision control;
- AI / GPU / private-credit modules as a separate modern-era validation layer.

## Core rule

A historical backtest may only use information that was actually available at the simulated decision time:

```text
available_at <= decision_time
```

Missing data is **missing**, not zero.

Stale data does not imply that the economic state returns to neutral. Instead, stale observations contribute increasing measurement uncertainty.

## Repository layout

```text
config/                  model and indicator definitions
docs/                    V6.1 specification and implementation notes
sql/                     point-in-time schema
src/global_regime_radar/ data contracts, signals, stress and backtest primitives
tests/                   invariants and regression tests
.github/workflows/       CI
```

## Status

This repository is an early research implementation. It is **not** an automated trading system and does not produce investment advice.

## License

Apache-2.0.
