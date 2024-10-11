from .league import League, LeagueSuccessModel
from .solo import Solo, SoloSuccessModel

type SummariesModel = SoloSuccessModel | LeagueSuccessModel

__all__ = [
    'League',
    'LeagueSuccessModel',
    'Solo',
    'SoloSuccessModel',
    'SummariesModel',
]
