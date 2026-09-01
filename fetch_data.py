
import subprocess

NFLVERSE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"


PLAYER_STATS_OLD_YEARS = range(2013, 2025)
PLAYER_STATS_NEW_YEARS = [2025]


SPECIAL_TEAMS_YEARS = [2023, 2024]

FILES = {}

for year in PLAYER_STATS_OLD_YEARS:
    FILES[f"player_stats_season_{year}.csv"] = (
        f"{NFLVERSE_BASE}/player_stats/player_stats_season_{year}.csv"
    )
for year in PLAYER_STATS_NEW_YEARS:
    FILES[f"player_stats_season_{year}.csv"] = (
        f"{NFLVERSE_BASE}/stats_player/stats_player_reg_{year}.csv"
    )
for year in SPECIAL_TEAMS_YEARS:
    FILES[f"kicking_season_{year}.csv"] = (
        f"{NFLVERSE_BASE}/player_stats/player_stats_kicking_season_{year}.csv"
    )
    FILES[f"def_season_{year}.csv"] = (
        f"{NFLVERSE_BASE}/player_stats/player_stats_def_season_{year}.csv"
    )

FILES["draft_picks.csv"] = f"{NFLVERSE_BASE}/draft_picks/draft_picks.csv"
FILES["games.csv"] = f"{NFLVERSE_BASE}/schedules/games.csv"
FILES["roster_2026.csv"] = f"{NFLVERSE_BASE}/rosters/roster_2026.csv"


def fetch_all():
    for filename, url in FILES.items():
        print(f"Downloading {filename} ...")
        subprocess.run(["curl", "-sL", "-f", "-o", filename, url], check=True)
    print(f"\nDone -- {len(FILES)} files downloaded.")


if __name__ == "__main__":
    fetch_all()
