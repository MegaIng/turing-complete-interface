from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import field, dataclass
from functools import cached_property
from itertools import groupby, zip_longest
from typing import Iterable, Any, Literal, Callable

from turing_complete_interface.circuit_compiler import Pos
from turing_complete_interface.circuit_parser import CircuitWire, GateReference, Circuit
from turing_complete_interface.level_layouts import get_layout
from turing_complete_interface.tc_components import get_component, get_custom_component
from turing_complete_interface.truth_table import TruthTable


@dataclass
class EntryConnector:
    combiner_custom_id: int
    creator_custom_id: int

    combiner_rel: Pos
    creator_rel: Pos

    combiner_wire_ends: tuple[tuple[Pos, ...], ...]
    creator_wires: tuple[tuple[Pos, ...], ...]

    group_in_rel: Pos
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


def straight_x_diag(start: Pos, end: Pos) -> Iterable[Pos]:
    yield start
    if start == end:
        return
    assert abs(start[1] - end[1]) < 2, (start, end)
    if abs(start[0] - end[0]) < 2:
        yield end
    elif start[0] > end[0]:
        yield from straight_x_diag((start[0] - 1, start[1]), end)
    else:
        yield from straight_x_diag((start[0] + 1, start[1]), end)


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
            0, self._next_id(), str(self.connector.combiner_custom_id), self.connector.combiner_custom_id))
        self.gates.append(out_c := GateReference(
            "Custom", (top_left[0] + self.connector.creator_rel[0], top_left[1] + self.connector.creator_rel[1]),
            0, self._next_id(), str(self.connector.creator_custom_id), self.connector.creator_custom_id))
        wire_x = top_left[0] + 1
        for i, (name, value) in enumerate(zip(self.input_names, inputs)):
            if value is None:
                continue
            old_wire = self.input_lines[name, value]
            target = self.connector.combiner_wire_ends[i]
            self.wires.append(CircuitWire(self._next_id(), "ck_bit", old_wire[0], "",
                                          list(straight(old_wire[1:],
                                                        p := (wire_x, old_wire[2])))))
            self.input_lines[name, value] = old_wire[0], *p
            self.wires.append(CircuitWire(self._next_id(), "ck_bit", 0, "", [
                p, *straight_y_diag((p[0] - 1, p[1] + 1), (target[0][0] + top_left[0], target[0][1] + top_left[1])),
                *((p[0] + top_left[0], p[1] + top_left[1]) for p in target[1:])
            ]))
        for wire, value in zip(self.connector.creator_wires, outputs):
            if value:
                self.wires.append(CircuitWire(self._next_id(), "ck_bit", 0, "",
                                              [(p[0] + top_left[0], p[1] + top_left[1]) for p in wire]))

        in_group = top_left[0] + self.connector.group_in_rel[0], top_left[1] + self.connector.group_in_rel[1]
        self.wires.append(
            CircuitWire(self._next_id(), "ck_byte", 0, "", list(straight_x_diag(self.output_pos, in_group))))
        out = top_left[0] + self.connector.out_rel[0], top_left[1] + self.connector.out_rel[1]
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
            self.wires.append(CircuitWire(self._next_id(), "ck_bit", c, "", list(straight((wx, wy), (x, wy)))))
            self.wires.append(
                CircuitWire(self._next_id(), "ck_bit", c, "", list(straight((x, wy), (x, wy + self.delta_y)))))
            self.input_lines[key] = (c, x, wy + self.delta_y)
            x += 1 if self.delta_x > 0 else -1
        self.wires.append(CircuitWire(self._next_id(), "ck_bit", 0, "",
                                      list(straight(self.output_pos, (x, self.output_pos[1])))))
        self.wires.append(CircuitWire(self._next_id(), "ck_bit", 0, "",
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
        # for i, ((inp, out), (next_inp, next_out)) in enumerate(zip(vs, vs[1:])):
        for i, (inp, out) in enumerate(vs):
            self.generate_entry(inp, out)
            if self.delta_x > 0:
                if self.next_x >= self.x_range.stop:
                    self.wrap_around()
            if self.delta_x < 0:
                if self.next_x <= self.x_range.start - self.delta_x * (total - i - 5):
                    self.wrap_around()


@dataclass
class ComponentTemplate:
    rel_pos: Pos
    kind: str
    extra_data: dict[str, Any] = field(default_factory=dict)

    @cached_property
    def shape(self):
        t = self.extra_data.get('custom_id', None)
        if t is None:
            t = self.extra_data.get('custom_data', None)
        return get_component(self.kind, t, True)[0]

    @property
    def right(self):
        left, _, width, _ = self.shape.bounding_box
        return self.rel_pos[0] + left + width

    @property
    def bottom(self):
        _, top, _, height = self.shape.bounding_box
        return self.rel_pos[1] + top + height

    @classmethod
    def lookup(cls, kind, topleft, custom_data=""):
        shape = get_component(kind, custom_data, True)[0]
        return cls((topleft[0] - shape.bounding_box[0], topleft[1] - shape.bounding_box[1]),
                   kind, {"custom_data": custom_data})

    @classmethod
    def lookup_custom(cls, name: str, topleft):
        cc = get_custom_component(name, True)
        return cls((topleft[0] - cc.shape.bounding_box[0], topleft[1] - cc.shape.bounding_box[1]),
                   name, {"custom_id": cc.id})


@dataclass
class WireTemplate:
    rel_path: tuple[Pos, ...]
    kind: str
    color: int = None


class PinSelector(ABC):
    @abstractmethod
    def find_pins(self, circuit: Circuit) -> list[tuple[tuple[int, int], tuple]]:
        raise NotImplementedError


@dataclass
class SortPins(PinSelector):
    base: PinSelector
    axis: Literal["x", "y", "xy", "yx"] = "y"

    def find_pins(self, circuit: Circuit) -> list[tuple[tuple[int, int], tuple]]:
        def key(t):
            return (t[0]["xy".index(self.axis[0])], t[0]["xy".index(self.axis[-1])])

        base = self.base.find_pins(circuit)
        return sorted(base, key=key)


@dataclass
class FilterPins(PinSelector):
    base: PinSelector
    filter: Callable[[tuple[int, int], tuple], bool]

    def find_pins(self, circuit: Circuit) -> list[tuple[tuple[int, int], tuple]]:
        return [p for p in self.base.find_pins(circuit) if self.filter(*p)]


class GateSelector(ABC):
    def find_gates(self, circuit: Circuit) -> list[GateReference]:
        raise NotImplementedError


@dataclass
class GatesByKind(GateSelector):
    kind: str | tuple[str, ...]

    def find_gates(self, circuit: Circuit) -> list[GateReference]:
        return [g for g in circuit.gates if ((g.name == self.kind)
                                             if isinstance(self.kind, str)
                                             else (g.name in self.kind))]


@dataclass
class CustomByName(GateSelector):
    name: str | tuple[str, ...]

    def find_gates(self, circuit: Circuit) -> list[GateReference]:
        return [g for g in circuit.gates if
                g.name == "Custom" and ((get_custom_component(g.custom_id, True).name.lower() == self.name.lower())
                                        if isinstance(self.name, str)
                                        else (get_custom_component(g.custom_id, True).name in self.name))]


@dataclass
class FromGates(PinSelector):
    gate_selector: GateSelector
    inputs: bool = False
    outputs: bool = False
    filter: Any = None

    def find_pins(self, circuit: Circuit) -> list[tuple[tuple[int, int], tuple]]:
        out = []
        for g in self.gate_selector.find_gates(circuit):
            shape = get_component(g.name, g.custom_id or g.custom_data, True)[0]
            for name, pin in shape.pins.items():
                if pin.is_input and self.inputs:
                    if self.filter is None or self.filter(name, pin):
                        out.append((g.translate(pin.pos), (GateReference, name, pin)))
                elif not pin.is_input and self.outputs:
                    if self.filter is None or self.filter(name, pin):
                        out.append((g.translate(pin.pos), (GateReference, name, pin)))
        return out


@dataclass
class Concatenate(PinSelector):
    parts: list[PinSelector]

    def find_pins(self, circuit: Circuit) -> list[tuple[tuple[int, int], tuple]]:
        return [p for s in self.parts for p in s.find_pins(circuit)]


@dataclass
class Pattern:
    components: list[ComponentTemplate] = field(default_factory=list)
    wires: list[WireTemplate] = field(default_factory=list)
    pins: dict[str, list[Pos]] = field(default_factory=dict)
    conditional_wires: dict[str, list[WireTemplate]] = field(default_factory=dict)
    score: tuple[int, int] = None

    @property
    def width(self):
        return max(c.right for c in self.components)

    @property
    def height(self):
        return max(c.bottom for c in self.components)

    def build(self, base: tuple[int, int], circuit: Circuit):
        circuit.nand += self.score[0]
        for c in self.components:
            circuit.add_component(c.kind, (base[0] + c.rel_pos[0], base[1] + c.rel_pos[1]), **c.extra_data)
        for w in self.wires:
            circuit.add_wire([(base[0] + x, base[1] + y) for x, y in w.rel_path], w.kind, color=w.color)
        return {
            category: [(base[0] + x, base[1] + y) for x, y in pins]
            for category, pins in self.pins.items()
        }

    @classmethod
    def from_circuit(cls, circuit: Circuit, pins: dict[str, PinSelector]):
        bounding_box = circuit.bounding_box(True)
        gates = []
        for g in circuit.gates:
            gates.append(ComponentTemplate((g.pos[0] - bounding_box[0], g.pos[1] - bounding_box[1]),
                                           g.name, {"custom_id": g.custom_id, "custom_data": g.custom_data,
                                                    "rotation": g.rotation}))
        wires = []
        for w in circuit.wires:
            wires.append(WireTemplate(
                tuple((x - bounding_box[0], y - bounding_box[1]) for x, y in w.positions),
                w.kind, w.color
            ))

        out = {}
        for cat, s in pins.items():
            out[cat] = [(t[0][0] - bounding_box[0], t[0][1] - bounding_box[1])
                        for t in s.find_pins(circuit)]
            if not out[cat]:
                print("For category", cat, "no values were produced by", s, "in circuit", circuit)
        return cls(gates, wires, out, score=(circuit.nand, circuit.delay))


@dataclass
class CompactTruthTableGenerator:
    """
    input_pattern: Input value (including pin) n 1bit output pins addressed pos[0:n],
                                               n 1bit output pins addressed neg[0:n]
    single_entry_pattern: n 1 bit pins addressed ins[0:n], result 1 1bit pin address out[0]
    double_entry_pattern: Two sets of n 1 bit pins, addressed a[0:n] and b[0:n], result 1 1bit address out[0]
    decoding_pattern: m bit input pins addressed values[0:k], ordered in increasing bit value
                    k ? bit input pins addressed prev[0:k], k ? bit output pins addressed 'next[0:k]'
    output_pattern: k ? bit input pins addressed prev[0:k], should include output pin or whatever is needed
    """
    input_pattern: Pattern
    single_entry_pattern: Pattern
    double_entry_pattern: Pattern
    decoding_pattern: Pattern
    output_pattern: Pattern

    def generate(self, truth: TruthTable, circuit=None, layout=None):
        def assign_inputs(selection, targets):
            i = 0
            for v, (pp, np) in zip(selection, zip(pos, neg)):
                if v is not None:
                    circuit.add_wire([np if v else pp, targets[i]], color=int(bool(v)))
                    i += 1

        if layout is None:
            layout = get_layout("component_factory")
        if circuit is None:
            circuit = Circuit([], [], random.randrange(0, 2 ** 32), nesting_level=2, description="Generate LUT")
            circuit.nand = 0
            circuit.delay = 4  # We assume
            circuit.store_score = True
        left, top, width, height = layout.area
        start_inner = layout.area[1] + self.input_pattern.width
        pins = self.input_pattern.build((left, top), circuit)
        pos = pins["pos"]
        neg = pins["neg"]
        current_x = start_inner
        current_y = layout.area[1]
        prev = None
        for result, values in truth.result_groups():
            last_out = None
            for a, b in zip_longest(values, values):
                if b is None:
                    if current_y + self.single_entry_pattern.height > layout.area[1] + layout.area[3]:
                        current_x += self.single_entry_pattern.width + 1
                        current_y = layout.area[1]
                    pins = self.single_entry_pattern.build((current_x, current_y), circuit)
                    assign_inputs(reversed(a), pins["ins"])
                    current_y += self.single_entry_pattern.height
                    if last_out is not None:
                        circuit.add_wire([last_out, pins["out"][0]])
                    last_out = pins["out"][0]
                else:
                    if current_y + self.double_entry_pattern.height > layout.area[1] + layout.area[3]:
                        current_x += self.double_entry_pattern.width
                        current_y = layout.area[1]
                    pins = self.double_entry_pattern.build((current_x, current_y), circuit)
                    assign_inputs(reversed(a), pins["a"])
                    assign_inputs(reversed(b), pins["b"])
                    current_y += self.double_entry_pattern.height
                    if last_out is not None:
                        circuit.add_wire([last_out, pins["out"][0]])
                    last_out = pins["out"][0]
            if last_out is not None:
                if current_y + self.decoding_pattern.height > layout.area[1] + layout.area[3]:
                    current_x += self.decoding_pattern.width
                    current_y = layout.area[1]
                pins = self.decoding_pattern.build((current_x, current_y), circuit)
                for p, v in zip(pins["values"], reversed(result)):
                    if v:
                        circuit.add_wire([last_out, p])
                if prev is not None:
                    circuit.add_wire([prev, pins["prev"][0]], "ck_byte")
                prev = pins["next"][0]
                current_y += self.decoding_pattern.height
        pins = self.output_pattern.build((layout.area[0] + layout.area[2] - self.output_pattern.width, layout.area[1]),
                                         circuit)
        if prev is not None:
            circuit.add_wire([prev, pins["prev"][0]], "ck_byte")

        return circuit


@dataclass
class HumanTruthTableGenerator:
    """
    input_pattern: Input value (including pin) n 1bit output pins addressed pos[0:n],
                                               n 1bit output pins addressed neg[0:n]
    single_entry_pattern: n 1 bit pins addressed ins[0:n], result 1 1bit pin address out[0]
    double_entry_pattern: Two sets of n 1 bit pins, addressed a[0:n] and b[0:n], result 1 1bit address out[0]
    decoding_pattern: m bit input pins addressed values[0:k], ordered in increasing bit value
                    k ? bit input pins addressed prev[0:k], k ? bit output pins addressed 'next[0:k]'
    output_pattern: k ? bit input pins addressed prev[0:k], should include output pin or whatever is needed
    """
    input_template: Pattern
    single_entry: Pattern
    double_entry: Pattern

    def generate(self, truth: TruthTable, circuit=None, layout=None):
        if layout is None:
            layout = get_layout("architecture")
        if circuit is None:
            circuit = Circuit([], [], 0)
        left, top, width, height = layout.area
        pins = self.input_template.build((left, top), circuit)
