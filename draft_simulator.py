from league_settings import RosterSettings

FLEX_ELIGIBLE = {'RB', 'WR', 'TE'}
SUPERFLEX_ELIGIBLE = {'QB', 'RB', 'WR', 'TE'}
BENCH_ELIGIBLE = {'QB', 'RB', 'WR', 'TE', 'K', 'DST'}


def build_roster_slots(roster: RosterSettings):
    """Build an ordered list of roster slots, each with the set of positions
    that can fill it. Order matters: dedicated position slots come first, so
    a player fills their 'natural' slot before we ever consider using them
    to fill FLEX/SUPERFLEX/bench -- this is a simple greedy assignment.
    """
    slots = []
    for _ in range(roster.qb):
        slots.append({'label': 'QB', 'eligible': {'QB'}, 'filled_by': None})
    for _ in range(roster.rb):
        slots.append({'label': 'RB', 'eligible': {'RB'}, 'filled_by': None})
    for _ in range(roster.wr):
        slots.append({'label': 'WR', 'eligible': {'WR'}, 'filled_by': None})
    for _ in range(roster.te):
        slots.append({'label': 'TE', 'eligible': {'TE'}, 'filled_by': None})
    for _ in range(roster.flex):
        slots.append({'label': 'FLEX', 'eligible': FLEX_ELIGIBLE, 'filled_by': None})
    for _ in range(roster.superflex):
        slots.append({'label': 'SUPERFLEX', 'eligible': SUPERFLEX_ELIGIBLE, 'filled_by': None})
    for _ in range(roster.k):
        slots.append({'label': 'K', 'eligible': {'K'}, 'filled_by': None})
    for _ in range(roster.dst):
        slots.append({'label': 'DST', 'eligible': {'DST'}, 'filled_by': None})
    for _ in range(roster.bench):
        slots.append({'label': 'BENCH', 'eligible': BENCH_ELIGIBLE, 'filled_by': None})
    return slots


class TeamRoster:
    """One team's roster slots. A league is just a list of these."""

    def __init__(self, roster: RosterSettings, team_number, is_user=False):
        self.team_number = team_number
        self.is_user = is_user
        self.slots = build_roster_slots(roster)

    def add_player(self, player_name, position):
        for slot in self.slots:
            if slot['filled_by'] is None and position in slot['eligible']:
                slot['filled_by'] = player_name
                return slot['label']
        return None  # roster already full at every slot this position could fill

    def open_positions(self):
        positions = set()
        for slot in self.slots:
            if slot['filled_by'] is None:
                positions |= slot['eligible']
        return positions

    def player_count(self):
        return sum(1 for slot in self.slots if slot['filled_by'] is not None)

    def label(self):
        return f"Team {self.team_number}" + (" (You)" if self.is_user else "")


class LeagueDraftState:
    """The live state of an entire draft: every team's roster, plus which
    players have been taken league-wide. `my_pick` is the 1-indexed team
    number the user is drafting as -- it can be changed at any time without
    losing anything already drafted, since it only flags which existing
    team is "yours."
    """

    def __init__(self, roster: RosterSettings, my_pick=1):
        self.roster = roster
        self.my_pick = my_pick
        self.teams = [
            TeamRoster(roster, i + 1, is_user=(i + 1 == my_pick))
            for i in range(roster.num_teams)
        ]
        self.drafted = set()
        self.pick_index = 0  # 0-indexed count of picks made so far, league-wide
        self.total_picks = roster.num_teams * roster.roster_size()

    def set_my_pick(self, my_pick):
        self.my_pick = my_pick
        for team in self.teams:
            team.is_user = (team.team_number == my_pick)

    def my_team(self):
        return self.teams[self.my_pick - 1]

    def is_draft_complete(self):
        return self.pick_index >= self.total_picks

    def team_on_the_clock(self):
        """Standard snake order: round 1 goes 1->N, round 2 goes N->1, round
        3 goes 1->N again, etc. This naturally gives the last team in a
        round back-to-back picks at the turn, without needing to special-
        case it -- the formula just falls out that way.
        """
        if self.is_draft_complete():
            return None
        n = self.roster.num_teams
        round_num, position_in_round = divmod(self.pick_index, n)
        if round_num % 2 == 0:
            team_number = position_in_round + 1
        else:
            team_number = n - position_in_round
        return self.teams[team_number - 1]

    def draft_player(self, player_name, position, team_number=None):
        """Assign a player to a specific team's roster and remove them from
        the league-wide available pool. Defaults to whoever is on the clock;
        every draft action advances the pick counter by one regardless of
        which team it's assigned to, since one real pick just happened."""
        if team_number is None:
            team_number = self.team_on_the_clock().team_number
        self.drafted.add(player_name)
        slot = self.teams[team_number - 1].add_player(player_name, position)
        self.pick_index += 1
        return slot


def recommend(board, drafted, team: TeamRoster, top_n=5):
    available = board[~board['player_display_name'].isin(drafted)]
    needed = team.open_positions()
    available = available[available['position'].isin(needed)]
    return available.sort_values('vorp', ascending=False).head(top_n)


def run_interactive(scoring=None, roster=None):
    from rankings import build_draft_board

    board = build_draft_board(scoring=scoring, roster=roster)
    roster = roster or RosterSettings()
    state = LeagueDraftState(roster=roster, my_pick=1)

    print("Draft assistant ready. Commands each turn:")
    print("  <player name>          -- mark as drafted, then enter the team number")
    print("  me <player name>       -- draft to your team")
    print("  board                  -- show top recommendations for your team")
    print("  roster <team number>   -- show that team's roster (blank = yours)")
    print("  quit                   -- exit\n")

    while True:
        cmd = input('> ').strip()
        if cmd.lower() == 'quit':
            break
        elif cmd.lower() == 'board':
            recs = recommend(board, state.drafted, state.my_team())
            print(recs[['player_display_name', 'position', 'projected_points', 'vorp']].to_string(index=False))
        elif cmd.lower().startswith('roster'):
            parts = cmd.split()
            team_number = int(parts[1]) if len(parts) > 1 else state.my_pick
            team = state.teams[team_number - 1]
            print(f"--- {team.label()} ---")
            for slot in team.slots:
                print(f"{slot['label']:>10}: {slot['filled_by'] or '(empty)'}")
        elif cmd.lower().startswith('me '):
            name = cmd[3:].strip()
            match = board[board['player_display_name'].str.lower() == name.lower()]
            if match.empty:
                print(f"'{name}' not found on the board.")
                continue
            position = match.iloc[0]['position']
            slot = state.draft_player(name, position, team_number=state.my_pick)
            print(f"Drafted {name} ({position}) to your {slot or 'NO OPEN SLOT'} slot.")
        else:
            name = cmd.strip()
            match = board[board['player_display_name'].str.lower() == name.lower()]
            if match.empty:
                print(f"'{name}' not found on the board.")
                continue
            position = match.iloc[0]['position']
            team_number = int(input(f'  Which team drafted {name}? (1-{roster.num_teams}): '))
            slot = state.draft_player(name, position, team_number=team_number)
            print(f"Drafted {name} ({position}) to Team {team_number}'s {slot or 'NO OPEN SLOT'} slot.")


if __name__ == '__main__':
    run_interactive()
