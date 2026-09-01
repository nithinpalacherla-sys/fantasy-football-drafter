import streamlit as st

from league_settings import ScoringSettings, RosterSettings
from rankings import build_draft_board
from draft_simulator import LeagueDraftState, recommend

st.set_page_config(page_title="Fantasy Football Draft Assistant", layout="wide")


def sidebar_settings():
    st.sidebar.header("League Settings")

    scoring_type = st.sidebar.selectbox("Scoring", ["PPR", "Half-PPR", "Standard"])
    scoring = {
        "PPR": ScoringSettings(),
        "Half-PPR": ScoringSettings.half_ppr(),
        "Standard": ScoringSettings.standard(),
    }[scoring_type]

    st.sidebar.subheader("Roster")
    num_teams = st.sidebar.number_input("Teams", 4, 20, 12)
    my_pick = st.sidebar.number_input("Your draft pick #", 1, num_teams, 1)
    qb = st.sidebar.number_input("QB", 0, 3, 1)
    rb = st.sidebar.number_input("RB", 0, 5, 2)
    wr = st.sidebar.number_input("WR", 0, 5, 2)
    te = st.sidebar.number_input("TE", 0, 3, 1)
    flex = st.sidebar.number_input("FLEX", 0, 3, 1)
    superflex = st.sidebar.number_input("SUPERFLEX", 0, 2, 0)
    k = st.sidebar.number_input("K", 0, 2, 1)
    dst = st.sidebar.number_input("DST", 0, 2, 1)
    bench = st.sidebar.number_input("Bench", 0, 10, 6)

    roster = RosterSettings(
        num_teams=num_teams, qb=qb, rb=rb, wr=wr, te=te,
        flex=flex, superflex=superflex, k=k, dst=dst, bench=bench,
    )
    return scoring, roster, my_pick


@st.cache_data(show_spinner="Building draft board (training models, this takes a few seconds)...")
def get_board(scoring: ScoringSettings, roster: RosterSettings):
    return build_draft_board(scoring=scoring, roster=roster)


def draft_board_page(board):
    st.header("Draft Board")

    positions = st.multiselect(
        "Filter by position", ['QB', 'RB', 'WR', 'TE', 'K', 'DST'],
        default=['QB', 'RB', 'WR', 'TE', 'K', 'DST'],
    )
    search = st.text_input("Search player name")

    view = board[board['position'].isin(positions)]
    if search:
        view = view[view['player_display_name'].str.contains(search, case=False)]

    display_cols = ['player_display_name', 'position', 'projected_points', 'projected_games', 'vorp', 'is_rookie_projection']
    view = view[display_cols].rename(columns={
        'player_display_name': 'Player', 'position': 'Pos', 'projected_points': 'Proj. Points',
        'projected_games': 'Proj. Games', 'vorp': 'VORP', 'is_rookie_projection': 'Rookie Est.',
    })
    st.dataframe(view, height=700, width='stretch')


POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']


def sync_team_dropdowns_to_clock(state: LeagueDraftState):
    """After any pick, every position tab's 'Drafted by' dropdown should
    default to whoever is now on the clock. The dropdowns are keyed on
    plain team *numbers* (not label text), so this just needs to push the
    new on-the-clock team's number into each widget's session_state slot --
    a number stays valid even when labels change (e.g. "(You)" moving to a
    different team), unlike matching against label strings.
    """
    on_the_clock = state.team_on_the_clock()
    if on_the_clock is None:
        return
    for position in POSITIONS:
        st.session_state[f"{position}_team"] = on_the_clock.team_number


def render_available_list(board, state: LeagueDraftState, position, key_prefix):
    """One position's available-player list, with a team-assignment control
    so a drafted player moves onto whichever team actually took them."""
    available = board[(board['position'] == position) & (~board['player_display_name'].isin(state.drafted))]
    available = available.sort_values('vorp', ascending=False)

    search = st.text_input("Search", key=f"{key_prefix}_search")
    view = available
    if search:
        view = view[view['player_display_name'].str.contains(search, case=False)]

    options = view['player_display_name'].tolist()
    if options:
        selected = st.selectbox("Select a player", options, key=f"{key_prefix}_select")

        team_numbers = [team.team_number for team in state.teams]
        on_the_clock = state.team_on_the_clock()
        default_team_number = on_the_clock.team_number if on_the_clock else state.my_pick
        team_number = st.selectbox(
            "Drafted by", team_numbers,
            index=team_numbers.index(default_team_number),
            format_func=lambda n: state.teams[n - 1].label(),
            key=f"{key_prefix}_team",
        )
        team_choice_label = state.teams[team_number - 1].label()

        if st.button(f"Draft {selected} to {team_choice_label}", type="primary", key=f"{key_prefix}_draft"):
            slot = state.draft_player(selected, position, team_number=team_number)
            st.success(f"Drafted {selected} ({position}) to {team_choice_label}'s {slot or 'NO OPEN SLOT'} slot.")
            st.rerun()
    else:
        st.caption("No available players left at this position.")

    st.dataframe(
        view.head(50)[['player_display_name', 'projected_points', 'vorp']]
        .rename(columns={'player_display_name': 'Player', 'projected_points': 'Proj. Points', 'vorp': 'VORP'}),
        width='stretch',
    )


def render_team_roster(team):
    st.write(f"**{team.label()}**")
    for slot in team.slots:
        status = slot['filled_by'] if slot['filled_by'] else '—'
        st.write(f"{slot['label']}: {status}")


def draft_simulator_page(board, roster, my_pick):
    roster_key = (roster.num_teams, roster.qb, roster.rb, roster.wr, roster.te,
                  roster.flex, roster.superflex, roster.k, roster.dst, roster.bench)

    if st.session_state.get('roster_key') != roster_key:
        st.session_state.draft_state = LeagueDraftState(roster=roster, my_pick=my_pick)
        st.session_state.roster_key = roster_key

    state = st.session_state.draft_state
    state.set_my_pick(my_pick)  # cheap to update every rerun; doesn't touch existing picks

    # Sync the "Drafted by" dropdowns to whoever is now on the clock, but
    # only right after the pick index actually changes -- and only here,
    # before any of the six position tabs' widgets are created this run.
    # Streamlit forbids writing to a widget's session_state key after that
    # widget has already been instantiated in the same script run, so this
    # must happen before the st.tabs() loop below, not inside a button
    # handler nested within it.
    if st.session_state.get('_synced_pick_index') != state.pick_index:
        sync_team_dropdowns_to_clock(state)
        st.session_state['_synced_pick_index'] = state.pick_index

    if st.button("Reset Draft"):
        st.session_state.draft_state = LeagueDraftState(roster=roster, my_pick=my_pick)
        st.rerun()

    on_the_clock = state.team_on_the_clock()
    if on_the_clock is None:
        st.success("Draft complete! Every roster is full.")
    elif on_the_clock.is_user:
        st.success(f"🔔 You're on the clock! (Pick {state.pick_index + 1}, {on_the_clock.label()})")
    else:
        st.info(f"On the clock: {on_the_clock.label()} (Pick {state.pick_index + 1})")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"Recommended picks for {state.my_team().label()}")
        recs = recommend(board, state.drafted, state.my_team(), top_n=10)
        st.dataframe(
            recs[['player_display_name', 'position', 'projected_points', 'vorp']]
            .rename(columns={'player_display_name': 'Player', 'position': 'Pos',
                              'projected_points': 'Proj. Points', 'vorp': 'VORP'}),
            width='stretch',
        )

        st.subheader("Available players by position")
        positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
        tabs = st.tabs(positions)
        for tab, position in zip(tabs, positions):
            with tab:
                render_available_list(board, state, position, key_prefix=position)

    with col2:
        st.subheader("League rosters")
        team_numbers = [team.team_number for team in state.teams]
        view_team_number = st.selectbox(
            "View team", team_numbers, index=state.my_pick - 1,
            format_func=lambda n: state.teams[n - 1].label(), key="view_team_select",
        )
        render_team_roster(state.teams[view_team_number - 1])

        st.divider()
        st.caption("Draft progress")
        progress_rows = [(t.label(), t.player_count()) for t in state.teams]
        st.dataframe(
            {"Team": [r[0] for r in progress_rows], "Players drafted": [r[1] for r in progress_rows]},
            width='stretch', hide_index=True,
        )


def main():
    st.title("Fantasy Football Draft Assistant")
    scoring, roster, my_pick = sidebar_settings()
    board = get_board(scoring, roster)

    page = st.sidebar.radio("Page", ["Draft Board", "Draft Simulator"])
    if page == "Draft Board":
        draft_board_page(board)
    else:
        draft_simulator_page(board, roster, my_pick)


if __name__ == '__main__':
    main()
