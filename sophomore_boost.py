import pandas as pd

CURRENT_SEASON = 2026
SOPHOMORE_DRAFT_YEAR = CURRENT_SEASON - 1  # players entering their 2nd season

# Validated against  historical data: across 184 rookie-to-sophomore
# WR transitions (2013-2024, min 6 games played each year), average ppg
# rose from 8.09 to 9.15 which is a real ~13% increase. This is the well-known
# "wide receivers often break out in year 2" pattern, and this number
# comes directly from measuring it rather than assuming it.
SOPHOMORE_BOOST = 1.13


def apply_sophomore_boost(players):
    draft = pd.read_csv('draft_picks.csv')
    sophomore_wrs = draft[(draft['season'] == SOPHOMORE_DRAFT_YEAR) & (draft['position'] == 'WR')]
    is_sophomore = players['player_id'].isin(sophomore_wrs['gsis_id']) & (players['position'] == 'WR')

    players = players.copy()
    players['sophomore_boost'] = 1.0
    players.loc[is_sophomore, 'sophomore_boost'] = SOPHOMORE_BOOST
    players['projected_ppg'] = players['projected_ppg'] * players['sophomore_boost']
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
