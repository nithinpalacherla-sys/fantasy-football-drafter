import pandas as pd


MIN_GAMES_THRESHOLD = 8


def find_vanished_players():
    
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
