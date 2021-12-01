from __future__ import annotations
from dataclasses import field, dataclass
from typing import Iterable

from turing_complete_interface.circuit_compiler import Pos
from turing_complete_interface.circuit_parser import CircuitWire, GateReference, Circuit
from turing_complete_interface.tc_components import get_component
from turing_complete_interface.truth_table import TruthTable


@dataclass
class EntryConnector:
    combiner_custom_id: int
    creator_custom_id: int

    combiner_rel: Pos
    creator_rel: Pos

    combiner_wire_ends: tuple[tuple[Pos, ...], ...]
    creator_wires: tuple[tuple[Pos, ...], ...]

    out_rel: Pos

    pair: tuple[EntryConnector, EntryConnector] = None


def straight_y_diag(start: Pos, end: Pos) -> Iterable[Pos]:
    yield start
    if start == end:
        return
    assert abs(start[0] - end[0]) < 2, (start, end)
    if abs(start[1] - end[1]) < 2:
        yield end
    elif start[1] > end[1]:
        yield from straight_y_diag((start[0], start[1] - 1), end)
    else:
        yield from straight_y_diag((start[0], start[1] + 1), end)


def straight(start: Pos, end: Pos) -> Iterable[Pos]:
    assert start[0] == end[0] or start[1] == end[1]
    yield start
    d = end[0] - start[0], end[1] - start[1]
    l = max(abs(d[0]), abs(d[1]))
    for i in range(1, l + 1):
        yield start[0] + d[0] * i // l, start[1] + d[1] * i // l


@dataclass
class TruthTableGenerator:
    input_names: tuple[str, ...]
    input_lines: dict[tuple[str, bool], tuple[int, int, int]]
    output_pos: tuple[int, int]
    component_y: int
    next_x: int
    delta_x: int
    delta_y: int
    x_range: range
    connector: EntryConnector
    permanent_id: int = None
    wires: list[CircuitWire] = field(default_factory=list)
    gates: list[GateReference] = field(default_factory=list)

    def _next_id(self):
        self.permanent_id += 1
        return self.permanent_id

    def generate_entry(self, inputs: tuple[bool | None, ...], outputs: tuple[bool | None, ...]):
        top_left = self.next_x, self.component_y
        self.next_x += self.delta_x
        self.gates.append(in_c := GateReference(
            "Custom", (top_left[0] + self.connector.combiner_rel[0], top_left[1] + self.connector.combiner_rel[1]),
            0, str(self._next_id()), str(self.connector.combiner_custom_id), self.connector.combiner_custom_id))
        self.gates.append(out_c := GateReference(
            "Custom", (top_left[0] + self.connector.creator_rel[0], top_left[1] + self.connector.creator_rel[1]),
            0, str(self._next_id()), str(self.connector.creator_custom_id), self.connector.creator_custom_id))
        wire_x = top_left[0] + 1
        for i, (name, value) in enumerate(zip(self.input_names, inputs)):
            if value is None:
                continue
            old_wire = self.input_lines[name, value]
            target = self.connector.combiner_wire_ends[i]
            self.wires.append(CircuitWire(self._next_id(), False, old_wire[0], "",
                                          list(straight(old_wire[1:],
                                                        p := (wire_x, old_wire[2])))))
            self.input_lines[name, value] = old_wire[0], *p
            self.wires.append(CircuitWire(self._next_id(), False, 0, "", [
                p, *straight_y_diag((p[0] - 1, p[1] + 1), (target[0][0] + top_left[0], target[0][1] + top_left[1])),
                *((p[0] + top_left[0], p[1] + top_left[1]) for p in target[1:])
            ]))
        print(self.connector.creator_wires, outputs)
        for wire, value in zip(self.connector.creator_wires, outputs):
            if value:
                self.wires.append(CircuitWire(self._next_id(), False, 0, "",
                                              [(p[0] + top_left[0], p[1] + top_left[1]) for p in wire]))
        out = top_left[0] + self.connector.out_rel[0], top_left[1] + self.connector.out_rel[1]
        self.wires.append(CircuitWire(self._next_id(), True, 0, "", list(straight(self.output_pos, out))))
        self.output_pos = out

    @staticmethod
    def build_inputs(y_start: int, x_start: int, pos_color: int, neg_color: int, lines: tuple[str | None, ...]):
        out = {}
        for l in lines:
            if l is None:
                y_start += 1
            else:
                out[l, False] = (pos_color, x_start, y_start)
                out[l, True] = (neg_color, x_start, y_start + 1)
                y_start += 2
        return out

    @classmethod
    def create(cls, tt: TruthTable, circuit: Circuit, entry: EntryConnector, lines, x_start=None, y_start=None,
               output_line=None):
        wire_start = min(y for _, _, y in lines.values())
        wire_end = max(y for _, _, y in lines.values())
        wire_width = wire_end - wire_start
        if y_start is None:
            y_start = wire_end + 2
        if x_start is None:
            x_start = max(x for _, x, _ in lines.values()) + 1
        if output_line is None:
            output_line = x_start, y_start + entry.out_rel[1]
        return cls(
            tt.in_vars,
            lines, output_line, y_start, x_start, 3, wire_width + entry.out_rel[1] + 4,
            range(x_start + wire_width, 127 - wire_width - 2), entry,
            max(max((w.id for w in circuit.wires), default=1), max((int(g.id) for g in circuit.gates), default=1)),
            circuit.wires, circuit.gates
        )

    def wrap_around(self):
        x = self.next_x
        for key, (c, wx, wy) in self.input_lines.items():
            self.wires.append(CircuitWire(self._next_id(), False, c, "", list(straight((wx, wy), (x, wy)))))
            self.wires.append(
                CircuitWire(self._next_id(), False, c, "", list(straight((x, wy), (x, wy + self.delta_y)))))
            self.input_lines[key] = (c, x, wy + self.delta_y)
            x += 1 if self.delta_x > 0 else -1
        self.wires.append(CircuitWire(self._next_id(), False, 0, "",
                                      list(straight(self.output_pos, (x, self.output_pos[1])))))
        self.wires.append(CircuitWire(self._next_id(), False, 0, "",
                                      list(straight((x, self.output_pos[1]), (x, self.output_pos[1] + self.delta_y)))))
        self.output_pos = (x, self.output_pos[1] + self.delta_y)

        x += 1 if self.delta_x > 0 else -1
        self.delta_x *= -1
        self.next_x += self.delta_x
        self.component_y += self.delta_y

    def apply(self, tt: TruthTable):
        total = len(tt.cares)
        vs = list(tt.cares.items())
        vs.sort(key=lambda t: t[1])
        for i, ((inp, out), (next_inp, next_out)) in enumerate(zip(vs, vs[1:])):
            self.generate_entry(inp, out)
            if self.delta_x > 0:
                if self.next_x >= self.x_range.stop:
                    self.wrap_around()
            if self.delta_x < 0:
                if self.next_x <= self.x_range.start-self.delta_x*(total-i-5):
                    self.wrap_around()
