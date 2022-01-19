from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product, groupby
from typing import Callable, Iterable, Literal

from bitarray import bitarray
from bitarray.util import int2ba, ba2int


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
        for ins in sorted(self.cares, key=lambda t: tuple(map(bool, self.cares[t]))):
            outs = self.cares[ins]
            rows.append(' ' + ' | '.join(map(get_symbol, ins)) + ' || ' + ' | '.join(map(get_symbol, outs)) + ' ')
        return '\n'.join(rows)

    @staticmethod
    def format_row(ins, outs):
        def get_symbol(v):
            if v is True:
                return '1'
            elif v is False:
                return '0'
            elif v is None:
                return 'x'
            else:
                return str(v)

        return ' ' + ' | '.join(map(get_symbol, ins)) + ' || ' + ' | '.join(map(get_symbol, outs)) + ' '

    def get(self, ins: tuple[bool | None, ...]) -> Iterable[tuple[tuple[bool | None, ...], tuple[bool | None, ...]]]:
        for k, v in self.cares.items():
            if all(a == b for a, b in zip(k, ins) if a is not None and b is not None):
                yield k, v

    def set(self, ins, out, unique: bool = False):
        assert len(ins) == len(self.in_vars), (ins, self.in_vars)
        assert len(out) == len(self.out_vars), (out, self.out_vars)
        if unique and any(witness := v for v in self.get(ins)):
            raise ValueError(f"Already exists {witness} (for {ins})")
        self.cares[ins] = out

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

    def prune_zeros(self):
        for k, v in list(self.cares.items()):
            if True not in set(v):
                del self.cares[k]

    def reduce_dupes(self):
        def similar(a_bits, b_bits) -> tuple[Literal["same", "one_diff", "incompatible"], int | None]:
            difference = None
            for i, (a, b) in enumerate(zip(a_bits, b_bits, strict=True)):
                if a != b:
                    # we also count one being None and the other being something else as a difference
                    # I am not sure if this hurts, but it reduces headaches later on ¯\_(ツ)_/¯
                    if difference is None:
                        difference = i
                    else:
                        return ("incompatible", None)
            if difference is None:
                return ("same", None)
            else:
                return ("one_diff", difference)

        TRIES = 10

        def combine(to_combine):
            out = None
            for j in range(TRIES):
                out = []
                for tc in to_combine:
                    for i, old in enumerate(out):
                        state, index = similar(tc, old)
                        if state == "incompatible":
                            continue
                        elif state == "same":
                            break
                        else:
                            out[i] = (*old[: index], None, *old[index + 1:])
                            break
                    else:
                        out.append(tc)
                to_combine = out
                if j % 2 == 1:
                    random.shuffle(to_combine)
                else:
                    to_combine.reverse()
            return out

        def dc(to_combine):
            if len(to_combine) > 10:
                for _ in range(TRIES):
                    l, r = dc(to_combine[:len(to_combine) // 2]), dc(to_combine[len(to_combine) // 2:])
                    assert len(l) + len(r) <= len(to_combine)
                    to_combine = list(set(l + r))
                    if len(to_combine) < 20:
                        break
                    random.shuffle(to_combine)
            return combine(to_combine)

        dupes = defaultdict(list)
        for k, v in self.cares.items():
            dupes[v].append(k)
        new_cares = {}
        for out, ins in dupes.items():
            old = len(ins)
            ins = dc(ins)
            new = len(ins)
            for k in ins:
                new_cares[k] = out
        self.cares = new_cares

    def split(self) -> Iterable[TruthTable]:
        return (
            TruthTable(self.in_vars, (ov,), {
                ins: (out[i],) for ins, out in self.cares.items()
            })
            for i, ov in enumerate(self.out_vars)
        )

    def fill_dont_cares(self):
        for e in product((False, True), repeat=len(self.in_vars)):
            if not any(self.get(e)):
                self.cares[e] = (None,) * len(self.out_vars)

    def to_csv(self):
        def s(v):
            if isinstance(v, str):
                return v
            elif isinstance(v, int):
                return '1' if v else '0'
            else:
                assert v is None, v
                return 'X'

        return "\n".join(
            ",".join((*map(s, row[:len(self.in_vars)]), '', *map(s, row[len(self.in_vars):])))
            for row in (
                (*self.in_vars, *self.out_vars),
                *((*i, *o) for i, o in self.cares.items())
            )
        )

    def result_groups(self):
        def key(t):
            return tuple({None: -1, False: 0, True: 1}[v] for v in t[1])

        return ((k, (i for i, _ in v)) for k, v in groupby(sorted(self.cares.items(), key=key), key=key))

    def to_espresso(self, include_names: bool = False):
        out = [
            f".i {len(self.in_vars)}",
            f".o {len(self.out_vars)}",
        ]
        if include_names:
            out += [
                f".ilb {' '.join(self.in_vars)}",
                f".ob {' '.join(self.out_vars)}",
            ]
        out += [
            '.type fdr',
            f'.p {len(self.cares)}'
        ]

        def entry(vs):
            return ''.join({None: '-', False: '0', True: '1'}[v] for v in vs)

        for entries, result in self.cares.items():
            out.append(f'{entry(entries)} {entry(result)}')
        out.append('.e')
        return '\n'.join(out)

    @classmethod
    def from_espresso(cls, text: str):
        in_vars = None
        out_vars = None
        cares = {}
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('#'):
                continue
            if line.startswith('.'):
                match line.split():
                    case '.i', n:
                        assert in_vars is None, (in_vars, line)
                        in_vars = [f'i{i}' for i in range(int(n))]
                    case '.o', n:
                        assert out_vars is None, (out_vars, line)
                        out_vars = [f'o{i}' for i in range(int(n))]
                    case ('.p' | '.e' | ('.p', _)):
                        pass
                    case _:
                        print(f"Unknown command line {line!r}, ignoring")
            elif in_vars is not None and out_vars is not None:
                current = []
                in_values = None
                out_values = None
                for c in line:
                    if c in '01-':
                        current.append({'0': False, '1': True, '-': None}[c])
                        if in_values is None:
                            if len(current) == len(in_vars):
                                in_values = current
                                current = []
                        elif len(current) == len(out_vars):
                            out_values = current
                            break
                else:
                    raise ValueError(line)
                cares[tuple(in_values)] = tuple(out_values)
        return cls(tuple(in_vars), tuple(out_vars), cares)

    def get_ord(self, ins) -> tuple[bool | None, ...]:
        out = [False] * len(self.out_vars)
        for i, r in self.get(ins):
            for j, v in enumerate(r):
                if v:
                    out[j] = True
        return tuple(out)


@dataclass
class LUTVariable:
    name: str
    bit_size: int
    aliases: dict[str | int, int | tuple[int | bool, ...]] = field(default_factory=dict)
    default: Literal["int", "tuple"] = "int"

    def to_bits(self, v) -> tuple[bool | None, ...]:
        if v in self.aliases:
            if v == self.aliases[v]:
                return v
            return self.to_bits(self.aliases[v])
        elif v is None:
            return (None,) * self.bit_size
        elif isinstance(v, int):
            return tuple(map(bool, int2ba(v, self.bit_size, 'big')))
        elif isinstance(v, tuple):
            return tuple((bool(a) if a is not None else None) for a in v)
        else:
            raise ValueError(v)

    def from_bits(self, bits: tuple[bool | None, ...]):
        inverse = {v: k for k, v in self.aliases.items()}
        if bits in inverse:
            return inverse[bits]
        if any(v is None for v in bits) or self.default == "tuple":
            return bits if any(v is not None for v in bits) else None
        i = ba2int(bitarray(bits, endian='big'))
        if i in inverse:
            return inverse[i]
        return i


@dataclass
class LUT:
    in_vars: tuple[LUTVariable, ...]
    out_vars: tuple[LUTVariable, ...]
    truth: TruthTable = None

    def __post_init__(self):
        if self.truth is None:
            self.truth = TruthTable(
                tuple(f"{var.name}{i}" for var in self.in_vars for i in range(var.bit_size)),
                tuple(f"{var.name}{i}" for var in self.out_vars for i in range(var.bit_size)),
            )

    def __str__(self):
        rows = []
        kw, vw = 0, 0
        for k, v in self.truth.cares.items():
            b = self.truth.format_row(k, v)
            k = str(self.decode_in(k))
            v = str(self.decode_out(v))
            rows.append((k, v, b))
            kw = max(len(k), kw)
            vw = max(len(v), vw)
        return '\n'.join(f'{k:>{kw}} -> {v:>{vw}} {b}' for k, v, b in rows)

    def set(self, inputs, outputs):
        in_bits = self.encode_in(inputs)
        out_bits = self.encode_out(outputs)
        try:
            self.truth.set(in_bits, out_bits, unique=True)
        except Exception as e:
            raise ValueError(f"Can't insert {inputs} -> {outputs}") from e

    def encode_in(self, values):
        if len(self.in_vars) == 1:
            try:
                return self.in_vars[0].to_bits(values)
            except ValueError:
                pass
        assert len(values) == len(self.in_vars), values

        return tuple(b for i, v in zip(self.in_vars, values, strict=True) for b in i.to_bits(v))

    def encode_out(self, values):
        if len(self.out_vars) == 1:
            try:
                return self.out_vars[0].to_bits(values)
            except ValueError:
                pass
        assert len(values) == len(self.out_vars), values
        return tuple(b for o, v in zip(self.out_vars, values, strict=True) for b in o.to_bits(v))

    def decode_in(self, bits):
        out = []
        for i in self.in_vars:
            out.append(i.from_bits(bits[:i.bit_size]))
            bits = bits[i.bit_size:]
        return tuple(out)

    def decode_out(self, bits):
        out = []
        for o in self.out_vars:
            out.append(o.from_bits(bits[:o.bit_size]))
            bits = bits[o.bit_size:]
        return tuple(out)

    def get(self, inputs):
        in_bits = self.encode_in(inputs)
        try:
            return map(lambda t: (self.decode_in(t[0]), self.decode_out(t[1])), self.truth.get(in_bits))
        except Exception as e:
            raise ValueError(f"Can't get {inputs}") from e

    def get_ord(self, inputs):
        return self.decode_out(self.truth.get_ord(self.encode_in(inputs)))


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
