import numpy as np
import pandas as pd
from projections import build_history, DEFAULT_YEARS

# How much real market appears to discount value for a player's own
# year-to-year inconsistency, by position. Calibrated to well-documented
# real ADP behavior: RB carries the largest risk discount (committee
# backfields, the highest injury rate of any position, and famously the
# lowest year-to-year statistical correlation of any skill position). QB
# carries the smallest (most stable, least likely to have touches
# reallocated to a teammate mid-season).
RISK_SENSITIVITY = {
    'QB': 0.05,
    'RB': 0.25,
    'WR': 0.12,
    'TE': 0.15,
}
MAX_DISCOUNT = 0.30


def compute_volatility(scoring=None, years=DEFAULT_YEARS):
    """Volatility = how much a player's ppg varies year to year, after
    removing any smooth improving/declining trend. A player who's simply
    gotten steadily better (or worse) every year isn't "inconsistent" in
    the risk sense real ADP is pricing in -- raw variance would incorrectly
    flag them. Removing the linear trend first isolates genuine up-and-down
    unpredictability instead.
    """
    history = build_history(years, scoring)

    def player_cv(group):
        group = group.sort_values('season')
        ppg = group['ppg'].to_numpy()
        n = len(ppg)
        if n < 3:
            return 0.0  # not enough points to distinguish trend from noise; assume no penalty
        x = np.arange(n)
        coeffs = np.polyfit(x, ppg, 1)
        trend = np.polyval(coeffs, x)
        residuals = ppg - trend
        mean_ppg = ppg.mean()
        return residuals.std() / mean_ppg if mean_ppg > 0 else 0.0

    return history.groupby('player_id').apply(player_cv).rename('cv').reset_index()


def apply_risk_adjustment(players, scoring=None):
    volatility = compute_volatility(scoring=scoring)
    players = players.merge(volatility, on='player_id', how='left')
    players['cv'] = players['cv'].fillna(0.0)

    sensitivity = players['position'].map(RISK_SENSITIVITY).fillna(0.1)
    players['risk_discount'] = (sensitivity * players['cv']).clip(upper=MAX_DISCOUNT)
    players['projected_ppg'] = players['projected_ppg'] * (1 - players['risk_discount'])
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
