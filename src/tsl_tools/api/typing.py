from typing import Literal

type S1ValidRank = Literal[
    'x+',
    'x',
    'u',
    'ss',
    's+',
    's',
    's-',
    'a+',
    'a',
    'a-',
    'b+',
    'b',
    'b-',
    'c+',
    'c',
    'c-',
    'd+',
    'd',
]
S1Rank = S1ValidRank | Literal['z']

type ValidRank = Literal['x+'] | S1ValidRank
type Rank = ValidRank | Literal['z']  # 未定级

type Summaries = Literal[
    '40l',
    'blitz',
    'league',
]
