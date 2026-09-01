import pandas as pd
from league_settings import ScoringSettings
from scoring import compute_fantasy_points

SEASON_LENGTH = 17
DEFAULT_YEARS = [2023, 2024, 2025]
# More recent seasons are more predictive of next season, so they get more weight.
DEFAULT_WEIGHTS = {2023: 0.2, 2024: 0.3, 2025: 0.5}

# nflverse renamed some columns starting with the 2025 release (part of a
# tag migration from "player_stats" to "stats_player"). Normalize old names
# so both schemas work with the same scoring code.
COLUMN_RENAMES = {'passing_interceptions': 'interceptions'}
# "Prior strength" in games-equivalent for regression to the mean: higher means
# we trust a player's own track record less and lean more on their position's
# average until they've built up a larger sample of games.
SHRINKAGE_GAMES = 6
# Durability gets a much stronger pull toward the position average than ppg
# does. A player's per-game rate (skill/role) is fairly stable and worth
# trusting; a couple of injury-shortened seasons are noisier and less
# predictive of next year specifically, so we lean harder on "most players
# play close to a full season" unless there's a long track record saying
# otherwise.
SHRINKAGE_GAMES_DURABILITY = 300
# Players with at least this many games in the window are treated as
# established, ongoing starters -- used to define a realistic "healthy
# starter" durability baseline, separate from backups/committee players
# who play little for reasons unrelated to injury.
ESTABLISHED_GAMES_THRESHOLD = 30
# How strongly target share (share of the team's total targets) adjusts a
# WR/TE's projected ppg, relative to their position's average share. This
# is a real, previously-unused signal: a player's share of their team's
# passing volume reflects their role independent of that team's overall
# pass volume, which matters a lot for players like Tetairoa McMillan (an
# elite 25% share on a low-volume offense) whose raw counting stats
# understate their real value. 1.5 means a player 10 points of share above
# average gets roughly a 15% ppg boost (and below-average share players
# get a corresponding discount).
TARGET_SHARE_WEIGHT = 1.5


def load_season_stats(year, scoring):
    df = pd.read_csv(f'player_stats_season_{year}.csv')
    df = df.rename(columns=COLUMN_RENAMES)
    df = df[df['season_type'] == 'REG'].fillna(0)
    df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    df['points'] = compute_fantasy_points(df, scoring)
    df['ppg'] = df['points'] / df['games'].replace(0, pd.NA)
    df['durability'] = df['games'] / SEASON_LENGTH
    # Weight by recency AND how many games that season actually represents --
    # otherwise a 3-game injury-shortened season gets the same say as a full
    # 17-game season just because they're both "the 2024 bucket," letting a
    # small, noisy sample swing the weighted average disproportionately.
    df['weight'] = DEFAULT_WEIGHTS[year] * df['games']
    df['season'] = year
    df['target_share'] = df.get('target_share', 0.0)
    return df[['player_id', 'player_display_name', 'position', 'games', 'ppg',
               'durability', 'weight', 'season', 'target_share']]


def build_history(years=DEFAULT_YEARS, scoring=None):
    scoring = scoring or ScoringSettings()
    frames = [load_season_stats(y, scoring) for y in years]
    history = pd.concat(frames, ignore_index=True)
    # a player with 0 games that season has an undefined (NaN) ppg; drop those rows
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

    # Regression to the mean: blend a player's own rate with their position's
    # average rate, weighted by how much real data we have on them. A player
    # with only a few games sampled leans heavily on the position average;
    # a multi-year starter leans almost entirely on their own track record.
    position_avg_ppg = players.groupby('position')['raw_ppg'].transform('mean')
    k = shrinkage_games
    players['projected_ppg'] = (
        players['games_sample'] * players['raw_ppg'] + k * position_avg_ppg
    ) / (players['games_sample'] + k)

    # Unlike ppg's shrinkage target, the right baseline here isn't "average
    # of everyone" -- backups and committee players play little for reasons
    # unrelated to health, which would drag the target down and make a
    # recent injury look *more* predictive than it should be. Restricting
    # to established players (a real, ongoing sample of games) gives a
    # realistic "healthy starter" baseline to regress an injury-shortened
    # season toward.
    established = players[players['games_sample'] >= ESTABLISHED_GAMES_THRESHOLD]
    position_avg_durability = established.groupby('position')['durability'].mean()
    players['position_avg_durability'] = players['position'].map(position_avg_durability)
    k_durability = shrinkage_games_durability
    players['projected_durability'] = (
        players['games_sample'] * players['durability'] + k_durability * players['position_avg_durability']
    ) / (players['games_sample'] + k_durability)

    # Target share adjustment: reward WR/TE whose share of their team's
    # targets is above their position's average (a low-volume-offense
    # alpha receiver like Tetairoa McMillan), and correspondingly discount
    # below-average-share players -- independent of raw counting stats.
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
