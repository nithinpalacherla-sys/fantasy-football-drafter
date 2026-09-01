import pandas as pd
from league_settings import ScoringSettings
from projections import COLUMN_RENAMES
from scoring import compute_fantasy_points
from situational_adjustments import SITUATIONAL_ADJUSTMENTS

BACKUP_THREAT_YEAR = 2025
SENSITIVITY = 0.35
MAX_DISCOUNT = 0.20


def compute_backup_threat(scoring=None, year=BACKUP_THREAT_YEAR):
  
    scoring = scoring or ScoringSettings()
    df = pd.read_csv(f'player_stats_season_{year}.csv')
    df = df.rename(columns=COLUMN_RENAMES)
    df = df[(df['season_type'] == 'REG') & (df['position'] == 'RB')].fillna(0)
    df['touches'] = df['carries'] + df['targets']
    df['points'] = compute_fantasy_points(df, scoring)
    df = df[df['touches'] > 0]
    df['points_per_touch'] = df['points'] / df['touches']

    
    current_rosters = pd.read_csv('roster_2026.csv')
    current_team = current_rosters.set_index('gsis_id')['team']
    df['current_team'] = df['player_id'].map(current_team)
    df = df.dropna(subset=['current_team'])

    results = []
    for team, group in df.groupby('current_team'):
        group = group.sort_values('touches', ascending=False)
        if len(group) < 2:
            continue
        rb1, rb2 = group.iloc[0], group.iloc[1]
        team_touches = group['touches'].sum()
        if rb1['points_per_touch'] == 0:
            continue

        backup_share = rb2['touches'] / team_touches
        efficiency_ratio = min(rb2['points_per_touch'] / rb1['points_per_touch'], 1.5)
        threat_score = backup_share * efficiency_ratio

        results.append({
            'player_id': rb1['player_id'],
            'player_display_name': rb1['player_display_name'],
            'backup_name': rb2['player_display_name'],
            'backup_share': backup_share,
            'threat_score': threat_score,
        })

    return pd.DataFrame(results)


def apply_backup_threat(players, scoring=None):
    threat = compute_backup_threat(scoring=scoring)
    players = players.merge(threat[['player_id', 'threat_score', 'backup_name']], on='player_id', how='left')
    players['threat_score'] = players['threat_score'].fillna(0.0)

    manual_multiplier = players['player_display_name'].map(SITUATIONAL_ADJUSTMENTS).fillna(1.0)
    has_manual_boost = manual_multiplier > 1.0
    is_rb = (players['position'] == 'RB') & ~has_manual_boost
    discount = (SENSITIVITY * players['threat_score']).clip(upper=MAX_DISCOUNT)
    players['backup_threat_discount'] = discount.where(is_rb, 0.0)

    players['projected_ppg'] = players['projected_ppg'] * (1 - players['backup_threat_discount'])
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
