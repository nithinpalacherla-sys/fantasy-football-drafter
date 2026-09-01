"""Downloads every real dataset this project depends on, all from
nflverse's public data releases (https://github.com/nflverse/nflverse-data).
Run this once after cloning the repo, before running any other script here.

Uses curl (via subprocess) rather than Python's urllib: some Python.org
macOS installs ship without a usable default CA bundle, which makes
urllib's HTTPS requests fail with a certificate verification error. curl
uses the system's own certificate store and works reliably here.
"""
import subprocess

NFLVERSE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"

# 2013-2024 use the older "player_stats" release; 2025+ uses the newer,
# consolidated "stats_player" release (nflverse migrated schemas partway
# through this project's data window -- see COLUMN_RENAMES in
# projections.py for the column-name differences this caused).
PLAYER_STATS_OLD_YEARS = range(2013, 2025)
PLAYER_STATS_NEW_YEARS = [2025]

# Kicker and defense stats were split into separate files under the old
# schema; the new schema merges them into the main player-stats file.
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
