from league_settings import ScoringSettings


def compute_fantasy_points(df, scoring: ScoringSettings):
    """Compute fantasy points per row directly from raw box-score stats,
    so we support any custom scoring settings rather than being stuck with
    whatever presets the raw data happens to include.
    """
    fumbles_lost = (
        df['sack_fumbles_lost']
        + df['rushing_fumbles_lost']
        + df['receiving_fumbles_lost']
    )
    two_point_conversions = (
        df['passing_2pt_conversions']
        + df['rushing_2pt_conversions']
        + df['receiving_2pt_conversions']
    )

    return (
        df['passing_yards'] * scoring.pass_yard
        + df['passing_tds'] * scoring.pass_td
        + df['interceptions'] * scoring.interception
        + df['rushing_yards'] * scoring.rush_yard
        + df['rushing_tds'] * scoring.rush_td
        + df['receptions'] * scoring.reception
        + df['receiving_yards'] * scoring.rec_yard
        + df['receiving_tds'] * scoring.rec_td
        + fumbles_lost * scoring.fumble_lost
        + two_point_conversions * scoring.two_point_conversion
        + df['special_teams_tds'] * scoring.special_teams_td
    )
