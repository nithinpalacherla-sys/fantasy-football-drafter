import pandas as pd
from league_settings import ScoringSettings
from scoring import compute_fantasy_points

SEASON_LENGTH = 17
DEFAULT_YEARS = [2023, 2024, 2025]

DEFAULT_WEIGHTS = {2023: 0.2, 2024: 0.3, 2025: 0.5}


COLUMN_RENAMES = {'passing_interceptions': 'interceptions'}

SHRINKAGE_GAMES = 6

SHRINKAGE_GAMES_DURABILITY = 300

ESTABLISHED_GAMES_THRESHOLD = 30

TARGET_SHARE_WEIGHT = 1.5


def load_season_stats(year, scoring):
    df = pd.read_csv(f'player_stats_season_{year}.csv')
    df = df.rename(columns=COLUMN_RENAMES)
    df = df[df['season_type'] == 'REG'].fillna(0)
    df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    df['points'] = compute_fantasy_points(df, scoring)
    df['ppg'] = df['points'] / df['games'].replace(0, pd.NA)
    df['durability'] = df['games'] / SEASON_LENGTH
    df['weight'] = DEFAULT_WEIGHTS[year] * df['games']
    df['season'] = year
    df['target_share'] = df.get('target_share', 0.0)
    return df[['player_id', 'player_display_name', 'position', 'games', 'ppg',
               'durability', 'weight', 'season', 'target_share']]


def build_history(years=DEFAULT_YEARS, scoring=None):
    scoring = scoring or ScoringSettings()
    frames = [load_season_stats(y, scoring) for y in years]
    history = pd.concat(frames, ignore_index=True)
    return history.dropna(subset=['ppg'])


def _weighted_avg(group, value_col):
    return (group[value_col] * group['weight']).sum() / group['weight'].sum()


def project_players(years=DEFAULT_YEARS, scoring=None, shrinkage_games=SHRINKAGE_GAMES,
                     shrinkage_games_durability=SHRINKAGE_GAMES_DURABILITY):
    history = build_history(years, scoring)
    grouped = history.groupby('player_id')

    players = pd.DataFrame({
        'player_display_name': grouped['player_display_name'].last(),
        'position': grouped['position'].last(),
        'raw_ppg': grouped.apply(lambda g: _weighted_avg(g, 'ppg')),
        'durability': grouped.apply(lambda g: _weighted_avg(g, 'durability')),
        'target_share': grouped.apply(lambda g: _weighted_avg(g, 'target_share')),
        'games_sample': grouped['games'].sum(),
    }).reset_index()

    
    position_avg_ppg = players.groupby('position')['raw_ppg'].transform('mean')
    k = shrinkage_games
    players['projected_ppg'] = (
        players['games_sample'] * players['raw_ppg'] + k * position_avg_ppg
    ) / (players['games_sample'] + k)

    
    established = players[players['games_sample'] >= ESTABLISHED_GAMES_THRESHOLD]
    position_avg_durability = established.groupby('position')['durability'].mean()
    players['position_avg_durability'] = players['position'].map(position_avg_durability)
    k_durability = shrinkage_games_durability
    players['projected_durability'] = (
        players['games_sample'] * players['durability'] + k_durability * players['position_avg_durability']
    ) / (players['games_sample'] + k_durability)

    
    is_pass_catcher = players['position'].isin(['WR', 'TE'])
    position_avg_target_share = players.groupby('position')['target_share'].transform('mean')
    share_premium = (players['target_share'] - position_avg_target_share) * TARGET_SHARE_WEIGHT
    players['target_share_multiplier'] = 1.0
    players.loc[is_pass_catcher, 'target_share_multiplier'] = 1 + share_premium[is_pass_catcher]
    players['projected_ppg'] = players['projected_ppg'] * players['target_share_multiplier']

    players['projected_games'] = (players['projected_durability'] * SEASON_LENGTH).round(1)
    players['projected_points'] = players['projected_ppg'] * players['projected_games']

    return players.sort_values('projected_points', ascending=False).reset_index(drop=True)


if __name__ == '__main__':
    projections = project_players()
    cols = ['player_display_name', 'position', 'projected_ppg', 'projected_games', 'projected_points']
    print(projections[cols].head(20).to_string(index=False))
