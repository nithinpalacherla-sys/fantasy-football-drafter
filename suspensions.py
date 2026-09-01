# Manually maintained list of known suspensions affecting games in the
# upcoming season. This can't be derived from historical stats -- it's
# current-events information that has to be updated by hand as news breaks.
# Games suspended is out of a 17-game season.
#
# Source (as of searching in August 2026): SI.com, NFL.com, CBS Sports.
SUSPENSIONS = {
    'Jeshaun Jones': 3,       # WR, violating substances of abuse policy
    'Dorance Armstrong': 1,   # personal conduct policy (not tracked position)
    'Nazeeh Johnson': 6,      # performance-enhancing substances (not tracked position)
    'Phidarian Mathis': 3,    # substances of abuse policy (not tracked position)
    'James Pearce Jr.': 8,    # (not tracked position)

    # NOTE: not a fixed-length suspension -- placed on the Commissioner's
    # Exempt List 2026-08-31 pending misdemeanor charges, with a court date
    # of 2026-11-17. No practicing/playing while exempt, but there's no
    # announced end date. 10 games is a rough placeholder estimate (roughly
    # Week 1 through the court date) and should be revised as the situation
    # develops -- this is the least reliable entry in this file.
    'Josh Jacobs': 10,
}


def apply_suspensions(players, season_length=17):
    """Discount projected games/points for any player on the suspension list.
    Matches by display name, so this is only as reliable as that name matching
    (duplicate names or formatting differences could cause a miss).
    """
    players = players.copy()
    suspended_games = players['player_display_name'].map(SUSPENSIONS).fillna(0)

    players['projected_games'] = (players['projected_games'] - suspended_games).clip(lower=0)
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
