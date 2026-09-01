from dataclasses import dataclass
import pandas as pd

SEASON_LENGTH = 17
DEFAULT_YEARS = [2023, 2024, 2025]
DEFAULT_WEIGHTS = {2023: 0.2, 2024: 0.3, 2025: 0.5}

POINTS_ALLOWED_TIERS = [
    (0, 10), (6, 7), (13, 4), (20, 1), (27, 0), (34, -1), (float('inf'), -4),
]


def points_allowed_score(points):
    for threshold, score in POINTS_ALLOWED_TIERS:
        if points <= threshold:
            return score


@dataclass
class KickerScoring:
    pat: float = 1.0
    fg_0_39: float = 3.0
    fg_40_49: float = 4.0
    fg_50_plus: float = 5.0


@dataclass
class DstScoring:
    sack: float = 1.0
    interception: float = 2.0
    fumble_recovery: float = 2.0
    safety: float = 2.0
    touchdown: float = 6.0


def compute_kicker_points(df, scoring: KickerScoring):
    short_makes = df['fg_made_0_19'] + df['fg_made_20_29'] + df['fg_made_30_39']
    long_makes = df['fg_made_40_49']
    bomb_makes = df['fg_made_50_59'] + df['fg_made_60_']
    return (
        df['pat_made'] * scoring.pat
        + short_makes * scoring.fg_0_39
        + long_makes * scoring.fg_40_49
        + bomb_makes * scoring.fg_50_plus
    )


def load_kicker_season(year):
    if year >= 2025:
        df = pd.read_csv(f'player_stats_season_{year}.csv')
        df = df[df['position'] == 'K']
    else:
        df = pd.read_csv(f'kicking_season_{year}.csv')
        df = df[(df['season_type'] == 'REG') & (df['position'] == 'K')]
    return df.fillna(0)


def project_kickers(years=DEFAULT_YEARS, scoring=None):
    scoring = scoring or KickerScoring()
    frames = []
    for year in years:
        df = load_kicker_season(year)
        df['points'] = compute_kicker_points(df, scoring)
        df['ppg'] = df['points'] / df['games'].replace(0, pd.NA)
        df['weight'] = DEFAULT_WEIGHTS[year]
        frames.append(df[['player_id', 'player_display_name', 'games', 'ppg', 'weight']].dropna(subset=['ppg']))

    history = pd.concat(frames, ignore_index=True)
    grouped = history.groupby('player_id')

    def weighted_avg(g):
        return (g['ppg'] * g['weight']).sum() / g['weight'].sum()

    players = pd.DataFrame({
        'player_display_name': grouped['player_display_name'].last(),
        'projected_ppg': grouped.apply(weighted_avg),
        'games_sample': grouped['games'].sum(),
    }).reset_index(drop=True)

    players['position'] = 'K'
    players['projected_games'] = SEASON_LENGTH  # kickers are rarely a durability concern in practice
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players.sort_values('projected_points', ascending=False).reset_index(drop=True)


# nflverse renamed/relocated some defensive columns starting with the 2025
# schema migration, same situation as the offensive stats in projections.py.
DEF_COLUMN_RENAMES = {'fumble_recovery_opp': 'def_fumble_recovery_opp', 'def_safeties': 'def_safety', 'recent_team': 'team'}


def load_defense_season(year):
    if year >= 2025:
        df = pd.read_csv(f'player_stats_season_{year}.csv')
    else:
        df = pd.read_csv(f'def_season_{year}.csv')
    df = df.rename(columns=DEF_COLUMN_RENAMES).fillna(0)
    return df[df['season_type'] == 'REG']


def team_points_allowed(games, year):
    season_games = games[(games['season'] == year) & (games['game_type'] == 'REG')]
    home = season_games[['home_team', 'away_score']].rename(columns={'home_team': 'team', 'away_score': 'points_allowed'})
    away = season_games[['away_team', 'home_score']].rename(columns={'away_team': 'team', 'home_score': 'points_allowed'})
    allowed = pd.concat([home, away], ignore_index=True)
    allowed['pa_score'] = allowed['points_allowed'].apply(points_allowed_score)
    return allowed.groupby('team').agg(
        points_allowed_score=('pa_score', 'sum'), games=('team', 'count')
    ).reset_index()


def load_team_defense_season(year, games):
    df = load_defense_season(year)
    counting = df.groupby('team').agg(
        sacks=('def_sacks', 'sum'),
        interceptions=('def_interceptions', 'sum'),
        fumble_recoveries=('def_fumble_recovery_opp', 'sum'),
        safeties=('def_safety', 'sum'),
        def_tds=('def_tds', 'sum'),
    ).reset_index()
    pa = team_points_allowed(games, year)
    return counting.merge(pa, on='team', how='inner')


def compute_dst_points(team_df, scoring: DstScoring):
    return (
        team_df['sacks'] * scoring.sack
        + team_df['interceptions'] * scoring.interception
        + team_df['fumble_recoveries'] * scoring.fumble_recovery
        + team_df['safeties'] * scoring.safety
        + team_df['def_tds'] * scoring.touchdown
        + team_df['points_allowed_score']
    )


def project_dst(years=DEFAULT_YEARS, scoring=None):
    scoring = scoring or DstScoring()
    games = pd.read_csv('games.csv')

    frames = []
    for year in years:
        team_df = load_team_defense_season(year, games)
        team_df['points'] = compute_dst_points(team_df, scoring)
        team_df['ppg'] = team_df['points'] / team_df['games']
        team_df['weight'] = DEFAULT_WEIGHTS[year]
        frames.append(team_df[['team', 'ppg', 'weight']])

    history = pd.concat(frames, ignore_index=True)
    grouped = history.groupby('team')
    projected_ppg = grouped.apply(lambda g: (g['ppg'] * g['weight']).sum() / g['weight'].sum())

    teams = pd.DataFrame({
        'player_display_name': projected_ppg.index + ' D/ST',
        'projected_ppg': projected_ppg.values,
    })
    teams['position'] = 'DST'
    teams['projected_games'] = SEASON_LENGTH
    teams['projected_points'] = teams['projected_ppg'] * teams['projected_games']
    return teams.sort_values('projected_points', ascending=False).reset_index(drop=True)


if __name__ == '__main__':
    print('--- Top 10 kickers ---')
    print(project_kickers()[['player_display_name', 'projected_ppg', 'projected_points']].head(10).to_string(index=False))
    print()
    print('--- Top 10 defenses ---')
    print(project_dst()[['player_display_name', 'projected_ppg', 'projected_points']].head(10).to_string(index=False))
