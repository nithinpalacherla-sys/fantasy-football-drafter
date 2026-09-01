import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from league_settings import ScoringSettings
from scoring import compute_fantasy_points
from projections import COLUMN_RENAMES, SEASON_LENGTH

ALL_YEARS = list(range(2013, 2026))
TEST_TARGET_YEAR = 2025          # the one year we hold out and never train on
BASE_FEATURES = ['prev_ppg', 'prev_games', 'prev_usage']

# how "usage" is measured differs by position -- these are the raw columns
# (summed, then divided by games) that make up a per-game workload signal.
# RB uses carries + targets (not just carries) since receiving work is a big
# share of value for modern pass-catching backs like McCaffrey or Kamara.
USAGE_COLUMNS = {
    'QB': ['attempts'],
    'RB': ['carries', 'targets'],
    'WR': ['targets'],
    'TE': ['targets'],
}

# Target share (% of the team's total targets) matters beyond raw target
# count for pass-catchers: a player commanding a big share of a low-volume
# offense (e.g. Tetairoa McMillan's 25% share on a run-heavy Panthers team)
# is a much better bet than raw counting stats suggest, since it reflects
# their role independent of their own team's overall pass volume. Not
# meaningful for QB (who doesn't receive targets) or as useful for RB
# (already captured via carries+targets usage), so this is WR/TE-only.
EXTRA_FEATURES = {
    'WR': ['prev_target_share'],
    'TE': ['prev_target_share'],
}


def features_for(position):
    return BASE_FEATURES + EXTRA_FEATURES.get(position, [])


def load_season(year, scoring):
    df = pd.read_csv(f'player_stats_season_{year}.csv')
    df = df.rename(columns=COLUMN_RENAMES)
    df = df[df['season_type'] == 'REG'].fillna(0)
    df = df[df['position'].isin(USAGE_COLUMNS.keys())].copy()
    df['points'] = compute_fantasy_points(df, scoring)
    df['ppg'] = df['points'] / df['games'].replace(0, pd.NA)
    return df


def build_pairs(position, scoring, years=ALL_YEARS):
    """One row per player per consecutive year-pair: features from year N,
    label = actual ppg in year N+1. This is the (input, correct-answer)
    training data supervised learning needs.
    """
    usage_cols = USAGE_COLUMNS[position]
    features = features_for(position)
    rows = []
    for year in years[:-1]:
        this_year = load_season(year, scoring)
        next_year = load_season(year + 1, scoring)
        this_year = this_year[this_year['position'] == position]
        next_year = next_year[next_year['position'] == position]

        this_year = this_year.assign(
            prev_ppg=this_year['ppg'],
            prev_games=this_year['games'],
            prev_usage=this_year[usage_cols].sum(axis=1) / this_year['games'].replace(0, pd.NA),
            prev_target_share=this_year.get('target_share', 0.0),
        )
        joined = this_year.merge(
            next_year[['player_id', 'ppg']], on='player_id', suffixes=('', '_next')
        )
        joined = joined.rename(columns={'ppg_next': 'target_ppg'})
        joined['target_year'] = year + 1
        rows.append(joined[['player_id', 'player_display_name', 'target_year'] + features + ['target_ppg']])

    return pd.concat(rows, ignore_index=True).dropna()


def train_and_evaluate(position, scoring=None):
    scoring = scoring or ScoringSettings()
    features = features_for(position)
    data = build_pairs(position, scoring)

    train = data[data['target_year'] < TEST_TARGET_YEAR]
    test = data[data['target_year'] == TEST_TARGET_YEAR]

    model = LinearRegression()
    model.fit(train[features], train['target_ppg'])

    predictions = model.predict(test[features])
    ml_mae = mean_absolute_error(test['target_ppg'], predictions)

    # Fair baseline comparison: what would our existing heuristic have said?
    # It only ever looks at prev_ppg (no usage feature), so this isolates
    # "does the extra signal + learned weights actually help."
    baseline_mae = mean_absolute_error(test['target_ppg'], test['prev_ppg'])

    return {
        'position': position,
        'model': model,
        'coefficients': dict(zip(features, model.coef_)),
        'intercept': model.intercept_,
        'ml_mae': ml_mae,
        'baseline_mae': baseline_mae,
        'n_train': len(train),
        'n_test': len(test),
    }


def predict_current_players(position, model, scoring=None, current_year=2025):
    """Use the trained model to predict next season's ppg for every player
    who actually played in `current_year`, using that season as the single
    most-recent lookback (this is what the model was trained to do)."""
    scoring = scoring or ScoringSettings()
    usage_cols = USAGE_COLUMNS[position]
    features = features_for(position)
    df = load_season(current_year, scoring)
    df = df[df['position'] == position].copy()

    df['prev_ppg'] = df['ppg']
    df['prev_games'] = df['games']
    df['prev_usage'] = df[usage_cols].sum(axis=1) / df['games'].replace(0, pd.NA)
    df['prev_target_share'] = df.get('target_share', 0.0)
    df = df.dropna(subset=features)

    df['ml_ppg'] = model.predict(df[features])
    return df[['player_id', 'player_display_name', 'ml_ppg']]


def blended_projections(scoring=None):
    """Combine the learned ML model with the existing heuristic model,
    weighting each by the inverse of its own measured test-set error --
    the model that was actually more accurate on held-out data gets more
    say in the final number. This is a simple, explainable ensemble.
    """
    from projections import project_players  # local import avoids a circular import

    scoring = scoring or ScoringSettings()
    heuristic = project_players(scoring=scoring)

    blended_frames = []
    for position in USAGE_COLUMNS:
        result = train_and_evaluate(position, scoring=scoring)
        ml_mae, baseline_mae = result['ml_mae'], result['baseline_mae']
        weight_ml = baseline_mae / (ml_mae + baseline_mae)
        weight_heuristic = ml_mae / (ml_mae + baseline_mae)

        ml_preds = predict_current_players(position, result['model'], scoring=scoring)
        position_players = heuristic[heuristic['position'] == position].merge(
            ml_preds[['player_id', 'ml_ppg']], on='player_id', how='left'
        )

        # players missing an ML prediction (no 2025 data to predict from,
        # e.g. injury/inactive) just fall back to the heuristic alone
        has_ml = position_players['ml_ppg'].notna()
        position_players['blended_ppg'] = position_players['projected_ppg']
        position_players.loc[has_ml, 'blended_ppg'] = (
            weight_ml * position_players.loc[has_ml, 'ml_ppg']
            + weight_heuristic * position_players.loc[has_ml, 'projected_ppg']
        )
        blended_frames.append(position_players)

    players = pd.concat(blended_frames, ignore_index=True)
    players['projected_ppg'] = players['blended_ppg']
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players.drop(columns=['blended_ppg', 'ml_ppg']).sort_values('projected_points', ascending=False).reset_index(drop=True)


if __name__ == '__main__':
    for position in USAGE_COLUMNS:
        result = train_and_evaluate(position)
        print(f"--- {position} (train n={result['n_train']}, test n={result['n_test']}) ---")
        print(f"  Learned coefficients: {result['coefficients']}")
        print(f"  Intercept: {result['intercept']:.2f}")
        print(f"  ML model MAE on {TEST_TARGET_YEAR}:        {result['ml_mae']:.3f}")
        print(f"  Baseline ('last year's ppg') MAE:  {result['baseline_mae']:.3f}")
        better = 'ML model' if result['ml_mae'] < result['baseline_mae'] else 'Baseline'
        print(f"  Winner: {better}")
        print()
