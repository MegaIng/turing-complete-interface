from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable


@dataclass
class TruthTable:
    in_vars: tuple[str, ...]
    out_vars: tuple[str, ...]
    cares: dict[tuple[bool | None, ...], tuple[bool | None, ...]] = field(default_factory=dict)

    def __str__(self):
        def get_symbol(v):
            if v is True:
                return '1'
            elif v is False:
                return '0'
            else:
                return 'x'

        rows = [' ' + ' | '.join(self.in_vars) + ' || ' + ' | '.join(self.out_vars) + ' ',
                '---+' * len(self.in_vars) + '+---' * len(self.out_vars)]
        for ins in sorted(self.cares):
            outs = self.cares[ins]
            rows.append(' ' + ' | '.join(map(get_symbol, ins)) + ' || ' + ' | '.join(map(get_symbol, outs)) + ' ')
        return '\n'.join(rows)

    def to_poses(self) -> tuple[PoS, ...]:
        sums = [[] for _ in self.out_vars]
        for ins, outs in self.cares.items():
            row = tuple(Atom(n, v) for n, v in zip(self.in_vars, ins) if v is not None)
            for ov, s in zip(outs, sums):
                if ov is False:
                    s.append(row)
        return tuple(PoS(name, s) for name, s in zip(self.out_vars, sums))

    def to_sopes(self) -> tuple[SoP, ...]:
        sums = [[] for _ in self.out_vars]
        for ins, outs in self.cares.items():
            row = tuple(Atom(n, not v) for n, v in zip(self.in_vars, ins) if v is not None)
            for ov, s in zip(outs, sums):
                if ov is True:
                    s.append(row)
        return tuple(SoP(name, s) for name, s in zip(self.out_vars, sums))

    @classmethod
    def from_function(cls, ins: tuple[str, ...], outs: tuple[str, ...],
                      f: Callable[[bool, ...], tuple[bool, ...]]) -> TruthTable:
        values = {}
        for arg in product((False, True), repeat=len(ins)):
            values[arg] = v = f(*arg)
            assert len(v) == len(outs), (v, outs)
        return cls(ins, outs, values)


@dataclass
class Atom:
    name: str
    inverted: bool = False

    def __str__(self):
        return self.name + ("'" if self.inverted else '')


@dataclass
class SoP:
    name: str
    products: list[tuple[Atom, ...]]

    def __str__(self):
        return f"{self.name} = ({') + ('.join(''.join(map(str, ts)) for ts in self.products)})"


@dataclass
class PoS:
    name: str
    sums: list[tuple[Atom, ...]]

    def __str__(self):
        return f"{self.name} = ({') * ('.join(' + '.join(map(str, ts)) for ts in self.sums)})"
