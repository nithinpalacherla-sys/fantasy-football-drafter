import pandas as pd
from league_settings import ScoringSettings
from scoring import compute_fantasy_points
from projections import COLUMN_RENAMES, SEASON_LENGTH


COHORT_YEARS = range(2013, 2026)


SHRINKAGE_ROOKIES = 8

SKILL_POSITIONS = ['QB', 'RB', 'WR', 'TE']


def _load_rookie_seasons(draft, year, scoring):
    stats = pd.read_csv(f'player_stats_season_{year}.csv')
    stats = stats.rename(columns=COLUMN_RENAMES)
    stats = stats[stats['season_type'] == 'REG'].fillna(0)
    stats['points'] = compute_fantasy_points(stats, scoring)

    rookies = draft[(draft['season'] == year) & (draft['position'].isin(SKILL_POSITIONS))]
    joined = rookies.merge(
        stats, left_on='gsis_id', right_on='player_id', how='inner', suffixes=('_draft', '_stat')
    )
    joined['rookie_ppg'] = joined['points'] / joined['games_stat'].replace(0, pd.NA)
    joined['rookie_durability'] = joined['games_stat'] / SEASON_LENGTH
    return joined[['round', 'position_draft', 'rookie_ppg', 'rookie_durability']].dropna(subset=['rookie_ppg'])


def build_cohort_table(scoring=None, cohort_years=COHORT_YEARS, shrinkage_rookies=SHRINKAGE_ROOKIES):
    scoring = scoring or ScoringSettings()
    draft = pd.read_csv('draft_picks.csv')

    frames = [_load_rookie_seasons(draft, year, scoring) for year in cohort_years]
    history = pd.concat(frames, ignore_index=True)
    history = history.rename(columns={'position_draft': 'position'})

    cohort = history.groupby(['round', 'position']).agg(
        raw_ppg=('rookie_ppg', 'mean'),
        raw_durability=('rookie_durability', 'mean'),
        n=('rookie_ppg', 'count'),
    ).reset_index()

    position_avg_ppg = cohort.groupby('position')['raw_ppg'].transform('mean')
    position_avg_durability = cohort.groupby('position')['raw_durability'].transform('mean')
    k = shrinkage_rookies

    cohort['projected_ppg'] = (cohort['n'] * cohort['raw_ppg'] + k * position_avg_ppg) / (cohort['n'] + k)
    cohort['projected_durability'] = (
        cohort['n'] * cohort['raw_durability'] + k * position_avg_durability
    ) / (cohort['n'] + k)

    return cohort


def project_incoming_rookies(draft_year, scoring=None, cohort=None):
    
    scoring = scoring or ScoringSettings()
    cohort = cohort if cohort is not None else build_cohort_table(scoring=scoring)

    draft = pd.read_csv('draft_picks.csv')
    incoming = draft[(draft['season'] == draft_year) & (draft['position'].isin(SKILL_POSITIONS))].copy()
    incoming = incoming.merge(cohort, on=['round', 'position'], how='left')

    incoming['projected_ppg'] = incoming['projected_ppg']
    incoming['projected_games'] = (incoming['projected_durability'] * SEASON_LENGTH).round(1)
    incoming['projected_points'] = incoming['projected_ppg'] * incoming['projected_games']
    incoming['player_display_name'] = incoming['pfr_player_name']
    incoming['is_rookie_projection'] = True

    cols = ['player_display_name', 'position', 'round', 'pick',
            'projected_ppg', 'projected_games', 'projected_points', 'is_rookie_projection']
    return incoming[cols].sort_values('projected_points', ascending=False).reset_index(drop=True)


if __name__ == '__main__':
    cohort = build_cohort_table()
    print('--- Cohort table (shrunk) ---')
    print(cohort.sort_values(['position', 'round'])[['round', 'position', 'raw_ppg', 'n', 'projected_ppg']].to_string(index=False))

    print()
    print('--- 2026 incoming rookie projections (top 15) ---')
    rookies = project_incoming_rookies(2026)
    print(rookies.head(15).to_string(index=False))
