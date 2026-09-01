import pandas as pd
from age_adjustment import apply_age_adjustment
from league_settings import ScoringSettings, RosterSettings, compute_replacement_ranks
from ml_projections import blended_projections
from backup_threat import apply_backup_threat
from risk_adjustment import apply_risk_adjustment
from rookie_projections import project_incoming_rookies
from situational_adjustments import apply_situational_adjustments
from sophomore_boost import apply_sophomore_boost
from special_teams import project_kickers, project_dst
from suspensions import apply_suspensions

ROOKIE_DRAFT_YEAR = 2026


def discount_lone_outliers(players, outlier_multiplier=2.0, discount_fraction=0.5):
    """VORP against a single fixed replacement level can't tell the
    difference between a real positional cliff (several players all far
    ahead of replacement) and one isolated outlier sitting atop an
    otherwise gently-sloped position (e.g. a TE having a historically
    huge season while TE2-TE6 are all close together). Real draft-day
    value is lower for the lone-outlier case, since passing on that
    player still leaves you a comparably good alternative next round.

    This flags a player as a "lone outlier" only when their gap to the
    next-best player at the position is unusually large *relative to
    that position's own typical gap* -- so it only fires for a real
    isolated case, and leaves positions with consistently large gaps
    (e.g. a deep, top-heavy RB class) untouched.
    """
    result_frames = []
    for position, pos_players in players.groupby('position'):
        pos_players = pos_players.sort_values('projected_points', ascending=False).reset_index(drop=True)
        points = pos_players['projected_points'].to_numpy().copy()
        n = len(points)

        gaps = [points[i] - points[i + 1] for i in range(n - 1)]
        median_gap = pd.Series(gaps).median() if gaps else 0

        dropoff_to_next = []
        for i in range(n):
            gap = points[i] - points[i + 1] if i + 1 < n else 0.0
            dropoff_to_next.append(gap)
            if median_gap > 0 and gap > outlier_multiplier * median_gap:
                excess = gap - median_gap
                points[i] -= discount_fraction * excess

        pos_players['projected_points'] = points
        pos_players['dropoff_to_next'] = dropoff_to_next
        result_frames.append(pos_players)

    return pd.concat(result_frames, ignore_index=True)


def compute_vorp(players, roster):
    replacement_ranks = compute_replacement_ranks(roster)
    replacement_level = {}
    for position, cutoff_rank in replacement_ranks.items():
        pos_players = players[players['position'] == position]
        if len(pos_players) >= cutoff_rank:
            replacement_level[position] = pos_players.sort_values(
                'projected_points', ascending=False
            ).iloc[cutoff_rank - 1]['projected_points']
        else:
            replacement_level[position] = pos_players['projected_points'].min()

    players['replacement_level'] = players['position'].map(replacement_level)
    players['vorp'] = players['projected_points'] - players['replacement_level']
    return players


def apply_positional_dampening(players, roster):
    """Raw VORP treats a point of value the same no matter which position
    it came from, but that's not quite right: RB/WR fill 2 dedicated
    lineup slots each (plus most of FLEX), while QB/TE/K/DST typically
    fill only 1. An elite QB or TE's edge over replacement can only ever
    be used once in your lineup, while an elite RB/WR's edge effectively
    gets "used" across multiple roster slots -- real draft-day value (and
    real ADP) reflects this, even though a single fixed-cutoff VORP number
    does not.

    We derive each position's "effective slots per team" straight from the
    same replacement-rank logic already used for VORP itself (dividing by
    the number of teams), then scale every position's VORP relative to
    whichever position has the most effective slots. This reuses the
    existing roster-settings math rather than introducing new constants,
    and it naturally adapts if you change the roster (e.g. superflex
    boosts QB's effective slot count and its dampening eases accordingly).
    """
    replacement_ranks = compute_replacement_ranks(roster)
    effective_slots = {pos: rank / roster.num_teams for pos, rank in replacement_ranks.items()}
    max_slots = max(effective_slots.values())
    dampening = {pos: slots / max_slots for pos, slots in effective_slots.items()}

    players = players.copy()
    players['positional_dampening'] = players['position'].map(dampening).fillna(1.0)
    players['draft_priority'] = players['vorp'] * players['positional_dampening']
    return players


def build_draft_board(scoring=None, roster=None, include_rookies=True):
    scoring = scoring or ScoringSettings()
    roster = roster or RosterSettings()

    players = blended_projections(scoring=scoring)
    players = apply_age_adjustment(players, scoring=scoring)
    players = apply_risk_adjustment(players, scoring=scoring)
    players = apply_backup_threat(players, scoring=scoring)
    players = apply_sophomore_boost(players)
    players = apply_situational_adjustments(players)
    players['is_rookie_projection'] = False

    if include_rookies:
        rookies = project_incoming_rookies(ROOKIE_DRAFT_YEAR, scoring=scoring)
        players = pd.concat([players, rookies], ignore_index=True, sort=False)

    kickers = project_kickers()
    kickers['is_rookie_projection'] = False
    dst = project_dst()
    dst['is_rookie_projection'] = False
    players = pd.concat([players, kickers, dst], ignore_index=True, sort=False)

    players = apply_suspensions(players)
    players = discount_lone_outliers(players)
    players = compute_vorp(players, roster)
    players = apply_positional_dampening(players, roster)

    return players.sort_values('draft_priority', ascending=False).reset_index(drop=True)


if __name__ == '__main__':
    board = build_draft_board()
    board.index += 1
    cols = ['player_display_name', 'position', 'projected_points', 'vorp', 'positional_dampening', 'draft_priority']
    print(board[cols].head(40).to_string())
