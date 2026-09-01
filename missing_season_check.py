import pandas as pd

# Players with at least this many games in an earlier season are "real"
# enough that their total disappearance from 2025 is worth investigating
# individually -- rather not miss a Mixon-style case, so this stays low.
MIN_GAMES_THRESHOLD = 8


def find_vanished_players():
    """Players who had meaningful playing time in 2023 or 2024 but have
    zero rows at all in the 2025 season file. A missing season currently
    just silently drops out of every model's data window -- this doesn't
    fix that on its own, it surfaces candidates for the kind of individual
    research we did for Joe Mixon (season-ending injury, release, retirement,
    etc.), since each case needs its own real explanation, not a blanket rule.
    """
    earlier = pd.concat([
        pd.read_csv('player_stats_season_2023.csv'),
        pd.read_csv('player_stats_season_2024.csv'),
    ], ignore_index=True)
    earlier = earlier[(earlier['season_type'] == 'REG') & (earlier['games'] >= MIN_GAMES_THRESHOLD)]
    earlier = earlier[earlier['position'].isin(['QB', 'RB', 'WR', 'TE'])]

    recent = pd.read_csv('player_stats_season_2025.csv')
    recent_ids = set(recent['player_id'])

    vanished = earlier[~earlier['player_id'].isin(recent_ids)]
    summary = vanished.groupby(['player_id', 'player_display_name', 'position']).agg(
        best_games=('games', 'max'),
        best_fantasy_ppr=('fantasy_points_ppr', 'max'),
    ).reset_index().sort_values('best_fantasy_ppr', ascending=False)

    return summary


if __name__ == '__main__':
    vanished = find_vanished_players()
    print(f"{len(vanished)} players had meaningful playing time in 2023/2024 but are entirely absent from 2025:\n")
    print(vanished.head(40).to_string(index=False))
