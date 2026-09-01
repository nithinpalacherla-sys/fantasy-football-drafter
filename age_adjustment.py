import pandas as pd

CURRENT_SEASON = 2026

# Rough real-world aging patterns: age past which production typically
# starts declining, and an approximate per-year decline rate past that
# point. RBs fall off earliest and fastest; QBs age most gracefully.
AGE_CURVES = {
    'QB': {'threshold': 36, 'decline_rate': 0.03},
    'RB': {'threshold': 28, 'decline_rate': 0.10},
    'WR': {'threshold': 30, 'decline_rate': 0.05},
    'TE': {'threshold': 30, 'decline_rate': 0.09},
}


def load_player_ages():
    draft = pd.read_csv('draft_picks.csv').dropna(subset=['age'])
    draft['current_age'] = draft['age'] + (CURRENT_SEASON - draft['season'])
    # a player can only be drafted once, but guard against any duplicate rows
    draft = draft.sort_values('season').drop_duplicates(subset='gsis_id', keep='last')
    return draft[['gsis_id', 'current_age']].rename(columns={'gsis_id': 'player_id'})


def age_multiplier(position, current_age):
    curve = AGE_CURVES.get(position)
    if curve is None or pd.isna(current_age):
        return 1.0
    years_past = max(0.0, current_age - curve['threshold'])
    return (1 - curve['decline_rate']) ** years_past


def compute_recent_trend(scoring=None):
    """Ratio of a player's most recent season's ppg to their earliest
    season's ppg within our data window. This is the direct evidence
    check the age curve is otherwise blind to: a player past the decline
    threshold whose own recent production hasn't actually dropped (or has
    improved) is real proof the generic aging prior doesn't apply to them
    -- exactly the judgment real analysts make for outliers like Derrick
    Henry, who has improved at ages 29-31 even though traditional aging
    curves say he's overdue to decline.
    """
    from projections import build_history, DEFAULT_YEARS
    history = build_history(DEFAULT_YEARS, scoring)

    def trend(g):
        g = g.sort_values('season')
        if len(g) < 2:
            return 1.0  # not enough seasons to measure a trend either way
        early_ppg, recent_ppg = g.iloc[0]['ppg'], g.iloc[-1]['ppg']
        return recent_ppg / early_ppg if early_ppg > 0 else 1.0

    return history.groupby('player_id').apply(trend).rename('recent_trend').reset_index()


def apply_age_adjustment(players, scoring=None):
    """Discount projected production for players past their position's
    typical decline age. Only applies where we can find a real draft-year
    age via player_id -- players without a match are left unadjusted.
    The discount is tempered by the player's own recent trend: real,
    measured evidence that they haven't actually declined outweighs the
    generic age-based prior.
    """
    ages = load_player_ages()
    players = players.merge(ages, on='player_id', how='left')
    curve_multiplier = pd.Series([
        age_multiplier(pos, age) for pos, age in zip(players['position'], players['current_age'])
    ], index=players.index)

    trend = compute_recent_trend(scoring=scoring)
    players = players.merge(trend, on='player_id', how='left')
    players['recent_trend'] = players['recent_trend'].fillna(1.0)

    # decline_evidence is 0 if the player's recent ppg matched or beat
    # their earlier ppg (no decline shown -- negate the curve's discount
    # entirely) and rises toward 1 the more their own data confirms a
    # real decline (in which case the full curve-based discount applies).
    # A floor keeps at least MIN_EVIDENCE_FLOOR of the curve's discount in
    # place even for a player with a flat/improving trend -- real market
    # still prices in some age risk even for proven outliers (Henry sits
    # at real ADP ~16, not a top-5 pick), so trend evidence should temper
    # the generic prior, not erase it completely.
    MIN_EVIDENCE_FLOOR = 0.41
    decline_evidence = (1 - players['recent_trend']).clip(lower=MIN_EVIDENCE_FLOOR, upper=1)
    raw_discount = 1 - curve_multiplier
    players['age_multiplier'] = 1 - raw_discount * decline_evidence

    players['projected_ppg'] = players['projected_ppg'] * players['age_multiplier']
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
