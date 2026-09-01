import pandas as pd
from league_settings import ScoringSettings
from projections import COLUMN_RENAMES
from scoring import compute_fantasy_points
from situational_adjustments import SITUATIONAL_ADJUSTMENTS

BACKUP_THREAT_YEAR = 2025
SENSITIVITY = 0.35
MAX_DISCOUNT = 0.20


def compute_backup_threat(scoring=None, year=BACKUP_THREAT_YEAR):
    """For each team's lead back (most touches last season), measure how
    real a threat their backup represents: the backup's share of the
    team's total RB touches, weighted by how efficient that backup was
    per touch relative to the starter. A backup who barely played, or who
    played a lot but was much less efficient, scores as a small threat; a
    backup who got real work AND produced well per touch scores high --
    this is meant to catch real committee risk (like Kyren Williams/Blake
    Corum) automatically instead of one team at a time by hand.
    """
    scoring = scoring or ScoringSettings()
    df = pd.read_csv(f'player_stats_season_{year}.csv')
    df = df.rename(columns=COLUMN_RENAMES)
    df = df[(df['season_type'] == 'REG') & (df['position'] == 'RB')].fillna(0)
    df['touches'] = df['carries'] + df['targets']
    df['points'] = compute_fantasy_points(df, scoring)
    df = df[df['touches'] > 0]
    df['points_per_touch'] = df['points'] / df['touches']

    # A player's team from last season's stats can be stale by the time we
    # actually draft (free agency, trades) -- exactly what happened with
    # Tyler Allgeier (Falcons in 2025, signed by Arizona in March 2026). Use
    # the current roster file to regroup players by their real 2026 team
    # instead of trusting last season's snapshot.
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

    # Only exclude players with a manual *boost* from the automatic signal
    # -- those reflect known, current news that a past committee threat is
    # now gone (e.g. Gibbs' 2025 backup was traded away), so a backward-
    # looking discount here would be flatly wrong. A manual *discount*
    # (Kyren Williams, Bucky Irving) reflects the same real phenomenon this
    # signal measures, just researched by hand -- the automatic signal
    # should reinforce it with real data, not get blocked by it. This
    # matters in practice: Irving's real automatic threat score turned out
    # to be much larger than our hand-estimated discount.
    manual_multiplier = players['player_display_name'].map(SITUATIONAL_ADJUSTMENTS).fillna(1.0)
    has_manual_boost = manual_multiplier > 1.0
    is_rb = (players['position'] == 'RB') & ~has_manual_boost
    discount = (SENSITIVITY * players['threat_score']).clip(upper=MAX_DISCOUNT)
    players['backup_threat_discount'] = discount.where(is_rb, 0.0)

    players['projected_ppg'] = players['projected_ppg'] * (1 - players['backup_threat_discount'])
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
