import numpy as np
import pandas as pd
from projections import build_history, DEFAULT_YEARS


RISK_SENSITIVITY = {
    'QB': 0.05,
    'RB': 0.25,
    'WR': 0.12,
    'TE': 0.15,
}
MAX_DISCOUNT = 0.30


def compute_volatility(scoring=None, years=DEFAULT_YEARS):
  
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
