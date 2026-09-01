# Fantasy Football Draft Assistant

**[Live app →](https://fantasy-football-drafter-twt7rgzxqojuqbehazdswe.streamlit.app)**

A fantasy football draft board and live draft simulator built on real NFL data,
combining a statistical projection model, a trained machine learning model, and
a set of researched real-world overrides (trades, injuries, suspensions, coaching
changes) — validated against real 2026 ADP data pulled from actual mock drafts.

Built as a from-scratch project to learn Python, pandas, and applied statistics/ML
through a domain I actually cared about, rather than a toy tutorial dataset.

## What it does

- **Draft board** — every QB/RB/WR/TE/K/DST ranked by projected value, using
  Value Over Replacement (VORP), with configurable league scoring (PPR/half-PPR/
  standard) and roster settings (team count, superflex, flex, bench size).
- **Draft simulator** — a live, multi-team draft tracker with proper **snake
  draft order** (team N naturally gets back-to-back picks at the turn), a "you're
  on the clock" indicator, per-position available-player lists, and a roster view
  for every team in the league, not just yours.
- **Web app** (Streamlit) — both of the above, interactively, in the browser.

## The modeling pipeline

Real historical stats alone aren't enough to draft well — a few things a pure
stats model structurally can't see turned out to matter a lot. This project layers
several signals on top of a real-data foundation:

1. **Historical projections** (`projections.py`) — a 3-year recency-weighted
   average of real per-game production, with shrinkage (regression to the mean)
   toward realistic position baselines. Durability (games played) is shrunk
   separately and much more aggressively than scoring rate, since one
   injury-shortened season is a much noisier signal than a player's per-game
   skill level.
2. **Machine learning model** (`ml_projections.py`) — a linear regression trained
   on 2013-2024 year-over-year data (train/test split by year to avoid lookahead
   bias), using target share as an engineered feature for WR/TE. Blended with the
   historical model, weighted by each model's own measured accuracy on a held-out
   test year — not an arbitrary 50/50 split.
3. **Rookie projections** (`rookie_projections.py`) — for players with zero NFL
   history, a draft-round + position cohort average built from 13 years of real
   draft outcomes, since a stats model has nothing to project from otherwise.
4. **Age curves with real-evidence override** (`age_adjustment.py`) — a generic
   decline curve per position, but tempered by each player's own measured
   year-over-year trend: a player whose production hasn't actually declined
   (e.g., a real aging-curve outlier) gets less of the generic penalty.
5. **Volatility and committee-risk discounts** (`risk_adjustment.py`,
   `backup_threat.py`) — RBs are priced with more downside risk than other
   positions in real fantasy markets (committee backfields, high injury rate,
   low year-to-year statistical correlation); this estimates that risk from a
   player's own detrended year-to-year variance and from how much their actual
   backup produced last season (using current 2026 rosters, not last year's team
   assignments, so a trade or release doesn't create a stale read).
6. **Situational overrides** (`situational_adjustments.py`, `suspensions.py`) —
   real, researched, sourced current events a trailing-stats model cannot see on
   its own: trades, coordinator changes, a torn Achilles that happened in the
   playoffs (after the entire data window ends), a season wiped out by injury
   with no games at all to reflect it.

## Validated against real market data

Rankings were checked against real 2026 PPR ADP (FantasyPros' consensus and
FantasyFootballCalculator's real mock-draft data) throughout development. Several
real, sourced discrepancies were found and fixed this way — a couple of examples:

- A player who'd missed his entire prior season with an injury was still ranked
  top-15 purely off older stats, because a fully missing season just silently
  drops out of a naive model's data window instead of raising a flag.
  `missing_season_check.py` now catches this systematically.
- A single historically dominant outlier at a normally-thin position (e.g. an
  elite TE season) was getting ranked as a top-5 overall pick, because raw
  Value-Over-Replacement can't distinguish "a real positional cliff" from "one
  outlier sitting atop an otherwise gently-sloped position."

## Setup

```bash
pip install -r requirements.txt
python3 fetch_data.py    # pulls real historical stats from nflverse (~13MB)
streamlit run app.py
```

## Project structure

```
league_settings.py       League config: scoring rules, roster construction
scoring.py                Raw box-score stats -> fantasy points
projections.py            Heuristic multi-year weighted projection model
ml_projections.py         Linear regression model + blend with the heuristic
rookie_projections.py     Draft-cohort model for players with no NFL history
special_teams.py          Kicker and team defense scoring/projections
age_adjustment.py         Position decline curves, tempered by real trend evidence
risk_adjustment.py        Statistical volatility/inconsistency discount
backup_threat.py          Real committee-risk signal from current-roster data
situational_adjustments.py  Manually researched current-event overrides
suspensions.py            Manually researched suspension overrides
sophomore_boost.py        Validated 2nd-year WR breakout adjustment
missing_season_check.py   Flags players who vanished from the data entirely
rankings.py               Combines every signal into one ranked draft board
draft_simulator.py        Multi-team league state, snake draft order, recommendations
app.py                    Streamlit web app
fetch_data.py             Downloads all real source data from nflverse
```

## Known limitations

- Season-long projections only — no in-season/weekly updates.
- Manual overrides (trades, injuries) require someone to notice and research
  the news; they aren't pulled from a live feed.
- Kicker/DST scoring uses standard point-per-kick and points-allowed tiers,
  which some leagues customize further.
