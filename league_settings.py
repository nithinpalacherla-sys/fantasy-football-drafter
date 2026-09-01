from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringSettings:
    
    pass_yard: float = 0.04       # 1 point per 25 passing yards
    pass_td: float = 4.0
    interception: float = -2.0
    rush_yard: float = 0.1        # 1 point per 10 rushing yards
    rush_td: float = 6.0
    reception: float = 1.0        # PPR = 1.0, half-PPR = 0.5, standard = 0.0
    rec_yard: float = 0.1
    rec_td: float = 6.0
    fumble_lost: float = -2.0
    two_point_conversion: float = 2.0
    special_teams_td: float = 6.0

    @classmethod
    def half_ppr(cls):
        return cls(reception=0.5)

    @classmethod
    def standard(cls):
        return cls(reception=0.0)


@dataclass(frozen=True)
class RosterSettings:
    
    num_teams: int = 12
    qb: int = 1
    rb: int = 2
    wr: int = 2
    te: int = 1
    flex: int = 1        # RB/WR/TE eligible
    superflex: int = 0   # QB/RB/WR/TE eligible
    k: int = 1
    dst: int = 1
    bench: int = 6

    def roster_size(self):
        return (self.qb + self.rb + self.wr + self.te + self.flex
                + self.superflex + self.k + self.dst + self.bench)



FLEX_SHARE = {'RB': 0.55, 'WR': 0.40, 'TE': 0.05}
SUPERFLEX_SHARE = {'QB': 0.70, 'RB': 0.10, 'WR': 0.15, 'TE': 0.05}


def compute_replacement_ranks(roster: RosterSettings):
    
    n = roster.num_teams
    ranks = {
        'QB': n * roster.qb,
        'RB': n * roster.rb,
        'WR': n * roster.wr,
        'TE': n * roster.te,
        'K': n * roster.k,
        'DST': n * roster.dst,
    }
    for pos, share in FLEX_SHARE.items():
        ranks[pos] += round(n * roster.flex * share)
    for pos, share in SUPERFLEX_SHARE.items():
        ranks[pos] += round(n * roster.superflex * share)
    return ranks
