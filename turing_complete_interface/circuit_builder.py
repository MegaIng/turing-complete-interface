from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, TYPE_CHECKING, Iterable, Literal

from bitarray import bitarray

from turing_complete_interface.circuit_parser import Circuit, GateReference, GateShape, CircuitWire, CircuitPin
from turing_complete_interface.truth_table import Atom
from turing_complete_interface.logic_nodes import CombinedLogicNode, NodePin
from turing_complete_interface.tc_components import get_component, rev_components

if TYPE_CHECKING:
    import pydot


@dataclass
class IOPosition:
    component_name: str
    pin_mapping: dict[str, str]
    force_id: str = None
    force_position: tuple[int, int] = None
    custom_data: str = ""

    @classmethod
    def from_circuit(cls, circuit: Circuit) -> list[IOPosition]:
        ios = []
        for gate in circuit.gates:
            shape, _ = get_component(gate.name, gate.custom_data)
            if not shape.is_io:
                continue
            ios.append(IOPosition(gate.name,
                                  {gate.id: next(iter(shape.pins))}
                                  if len(shape.pins) == 1 else {
                                      f"{gate.id}.{pin_name}": pin_name for pin_name in shape.pins
                                  }, gate.id, gate.pos, gate.custom_data))
        return ios

    @classmethod
    def from_node(cls, node: CombinedLogicNode) -> list[IOPosition]:
        ios = []
        for name, inp in node.inputs.items():
            ios.append(IOPosition("Input1" if inp.bits == 1 else "Input1B",
                                  {name: "value"}, custom_data=name))
        for name, out in node.outputs.items():
            ios.append(IOPosition("Output1" if out.bits == 1 else "Output1B",
                                  {name: "value"}, custom_data=name))
        return ios


@dataclass
class Space:
    x: int
    y: int
    w: int
    h: int
    _observer: Any = None
    _placed_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    _protected: set[Any] = field(default_factory=set)
    _taken_spaces: bitarray = None

    def __post_init__(self):
        self._taken_spaces = bitarray([0] * (self.w * self.h))
        self._taken_spaces[:] = 0

    def place(self, w: int, h: int, force_pos: tuple[int, int] = None,
              hasher: Callable[[tuple[int, int]], Any] = None) -> tuple[int, int]:
        if force_pos is None:
            for idx in self._taken_spaces.itersearch(bitarray([0] * w)):
                y, x = divmod(idx, self.w)
                if x + w > self.w:
                    continue
                if hasher is not None and hasher((x + self.x, y + self.y)) in self._protected:
                    continue
                for k in range(h):
                    if idx + k * self.w + w >= self.h * self.w:
                        break
                    if self._taken_spaces[idx + k * self.w:idx + k * self.w + w].any():
                        break
                else:
                    break
            else:
                raise ValueError(f"No space left {w}, {h}")
        else:
            x, y = force_pos

        self._placed_boxes.append((x, y, w, h))
        idx = y * self.w + x
        for k in range(h):
            self._taken_spaces[idx + k * self.w:idx + k * self.w + w] = 1
        if hasher is not None:
            self._protected.add(hasher((x + self.x, y + self.y)))
        if self._observer is not None:
            self._observer(self)
        return x + self.x, y + self.y

    def is_filled(self, x: int, y: int):
        return self._taken_spaces[(y - self.y) * self.w + (x - self.x)]


def build_circuit(node: CombinedLogicNode, io_positions: list[IOPosition], space: Space,
                  level_version: int = 0, place_alone: Collection[str] = (), place_memory_alone=True) -> Circuit:
    taken_ids: set[int] = set()
    i = 1

    def get_id() -> int:
        nonlocal i
        while i in taken_ids:
            i += 1
        taken_ids.add(i)
        return i

    def place(shape: GateShape, io: bool = False, forced_pos: tuple[int, int] = None):
        ox, oy, w, h = shape.bounding_box

        def translate(p):
            return (int((p[0] + 30 - ox) // 8 - 3), int((p[1] + 30 - oy) // 8 - 3))

        if forced_pos is not None:
            forced_pos = forced_pos[0] + ox - space.x, forced_pos[1] + ox - space.y

        t, l = space.place(w, h, forced_pos, (translate if io else None))
        return t - ox, l - oy

    gate_refs = []
    pin_locations: dict[NodePin, tuple[CircuitPin, int, int]] = {}
    for io in io_positions:
        shape, _ = get_component(io.component_name, io.custom_data)
        pos = place(shape, True, io.force_position)
        gi = get_id() if io.force_id is None else io.force_id

        gate_refs.append(GateReference(io.component_name, pos, 0, str(gi), io.custom_data))

        for node_pin_name, shape_pin_name in io.pin_mapping.items():
            dp = shape.pins[shape_pin_name].pos
            pin_locations[None, node_pin_name] = shape.pins[shape_pin_name], pos[0] + dp[0], pos[1] + dp[1]

    for name, n in node.nodes.items():
        component_name, custom_data = rev_components[n.name]
        shape, inner_node = get_component(component_name, custom_data, no_node=True)
        pos = place(shape, (n.name in place_alone)
                    or (name in place_alone)
                    or (place_memory_alone and inner_node.state_size != 0))
        gi = get_id()

        gate_refs.append(GateReference(component_name, pos, 0, str(gi), custom_data))

        for node_pin_name, pin in shape.pins.items():
            dp = pin.pos
            pin_locations[name, node_pin_name] = pin, pos[0] + dp[0], pos[1] + dp[1]

    wires = []

    splitters = {}
    makers = {}
    bs_shape = get_component("ByteSplitter", "")[0]
    bm_shape = get_component("ByteMaker", "")[0]
    for wire in node.wires:
        source_pin, *start = pin_locations[wire.source]
        target_pin, *end = pin_locations[wire.target]
        start = tuple(start)
        end = tuple(end)
        if not source_pin.is_byte and not target_pin.is_byte:
            assert wire.source_bits == wire.target_bits == (0, 1), wire
            wires.append(CircuitWire(len(wires) + 1, False, 0, "", [tuple(start), tuple(end)]))
        elif source_pin.is_byte and not target_pin.is_byte:
            assert wire.target_bits == (0, 1)
            if start not in splitters:
                pos = place(bs_shape)
                splitter = splitters[start] = GateReference("ByteSplitter", pos, 0, str(get_id()), "")
                gate_refs.append(splitter)
                wires.append(CircuitWire(get_id(), True, 0, "", [start, bs_shape.pin_position(splitter, "in")]))
            else:
                splitter = splitters[start]
            wires.append(CircuitWire(get_id(), False, 0, "",
                                     [bs_shape.pin_position(splitter, f"r{wire.source_bits[0]}"), end]))
        elif not source_pin.is_byte and target_pin.is_byte:
            assert wire.source_bits == (0, 1)
            if end not in makers:
                pos = place(bm_shape)
                maker = makers[end] = GateReference("ByteMaker", pos, 0, str(get_id()), "")
                gate_refs.append(maker)
                wires.append(CircuitWire(get_id(), True, 0, "", [bm_shape.pin_position(maker, "out"), end]))
            else:
                maker = makers[end]
            wires.append(CircuitWire(get_id(), False, 0, "",
                                     [start, bm_shape.pin_position(maker, f"r{wire.target_bits[0]}")]))
        else:
            assert False, wire
    return Circuit(gate_refs, wires, 99_999, 99_999, level_version)


def to_pydot(node: CombinedLogicNode, io_positions: list[IOPosition], space: Space) -> \
        tuple[dict[str, tuple[str, IOPosition]], "pydot.Dot"]:
    import pydot

    g = pydot.Dot(graph_type="digraph", rankdir="LR", nodesep=1, ranksep=5, splines="ortho")

    for name, ln in node.nodes.items():
        component_name, custom_data = rev_components[ln.name]
        shape, inner_node = get_component(component_name, custom_data, no_node=True)
        g.add_node(pydot.Node(name, fixedsize=True, shape="box",
                              width=shape.bounding_box[2], height=shape.bounding_box[3],
                              label=f"{component_name}[{name}]"))
    io_nodes = {}
    for io in io_positions:
        shape, _ = get_component(io.component_name, io.custom_data)
        name = "".join(io.pin_mapping)
        for p in io.pin_mapping:
            io_nodes[p] = name, io
        g.add_node(pydot.Node(name, fixedsize=True, shape="box",
                              width=7, height=7,
                              label=f"{io.component_name}[{name}]"))

    for wire in node.wires:
        if wire.source[0] is None:
            source = io_nodes[wire.source[1]][0]
        else:
            source = wire.source[0]
        if wire.target[0] is None:
            target = io_nodes[wire.target[1]][0]
        else:
            target = wire.target[0]
        g.add_edge(pydot.Edge(source, target, tailport="e", headport="w", ))
    return io_nodes, g


def layout_with_pydot(node: CombinedLogicNode, io_positions: list[IOPosition], space: Space) -> Circuit:
    i = 1
    taken_ids = set()

    def get_id() -> int:
        nonlocal i
        while i in taken_ids:
            i += 1
        taken_ids.add(i)
        return i

    pin_to_io, graph = to_pydot(node, io_positions, space)
    graph.write_svg("test.svg")
    data = json.loads(graph.create(format='json0'))
    del graph
    ionames = {name: io for name, io in pin_to_io.values()}
    gate_refs = []
    pin_locations = {}

    for obj in data["objects"]:
        name, pos = obj['name'], obj['pos']
        pos = pos.split(',')
        pos = int(pos[0]) // 72 + space.x, int(pos[1]) // 72 + space.y
        if name in ionames:
            io: IOPosition = ionames[name]
            if io.force_id is not None:
                gid = int(io.force_id)
                taken_ids.add(gid)
            else:
                gid = get_id()
            component_name, custom_data = io.component_name, io.custom_data
            gate_refs.append(GateReference(io.component_name, pos, 0, str(gid), io.custom_data))
            shape, _ = get_component(io.component_name, io.custom_data, True)

            for node_pin_name, shape_pin_name in io.pin_mapping.items():
                dp = shape.pins[shape_pin_name].pos
                pin_locations[None, node_pin_name] = shape.pins[shape_pin_name], pos[0] + dp[0], pos[1] + dp[1]
        else:
            n = node.nodes[name]
            component_name, custom_data = rev_components[n.name]
            shape, inner_node = get_component(component_name, custom_data, no_node=True)
            gid = get_id()
            for node_pin_name, pin in shape.pins.items():
                dp = pin.pos
                pin_locations[name, node_pin_name] = pin, pos[0] + dp[0], pos[1] + dp[1]

        space.place(shape.bounding_box[2], shape.bounding_box[3], (pos[0] - space.x, pos[1] - space.y))
        gate_refs.append(GateReference(component_name, pos, 0, str(gid), custom_data))

    wires = []

    splitters = {}
    makers = {}
    bs_shape = get_component("ByteSplitter", "")[0]
    bm_shape = get_component("ByteMaker", "")[0]
    for wire in node.wires:
        source_pin, *start = pin_locations[wire.source]
        target_pin, *end = pin_locations[wire.target]
        start = tuple(start)
        end = tuple(end)
        if not source_pin.is_byte and not target_pin.is_byte:
            assert wire.source_bits == wire.target_bits == (0, 1), wire
            wires.append(CircuitWire(len(wires) + 1, False, 0, "", [tuple(start), tuple(end)]))
        elif source_pin.is_byte and not target_pin.is_byte:
            assert wire.target_bits == (0, 1)
            if start not in splitters:
                t, l = space.place(bm_shape.bounding_box[2], bm_shape.bounding_box[3])
                pos = t - bm_shape.bounding_box[0], l - bm_shape.bounding_box[1]
                splitter = splitters[start] = GateReference("ByteSplitter", pos, 0, str(get_id()), "")
                gate_refs.append(splitter)
                wires.append(CircuitWire(get_id(), True, 0, "", [start, bs_shape.pin_position(splitter, "in")]))
            else:
                splitter = splitters[start]
            wires.append(CircuitWire(get_id(), False, 0, "",
                                     [bs_shape.pin_position(splitter, f"r{wire.source_bits[0]}"), end]))
        elif not source_pin.is_byte and target_pin.is_byte:
            assert wire.source_bits == (0, 1)
            if end not in makers:
                t, l = space.place(bm_shape.bounding_box[2], bm_shape.bounding_box[3])
                pos = t - bm_shape.bounding_box[0], l - bm_shape.bounding_box[1]
                maker = makers[end] = GateReference("ByteMaker", pos, 0, str(get_id()), "")
                gate_refs.append(maker)
                wires.append(CircuitWire(get_id(), True, 0, "", [bm_shape.pin_position(maker, "out"), end]))
            else:
                maker = makers[end]
            wires.append(CircuitWire(get_id(), False, 0, "",
                                     [start, bm_shape.pin_position(maker, f"r{wire.target_bits[0]}")]))
        else:
            assert False, wire

    return Circuit(gate_refs, wires)


GateType = Literal["and", "or", "nor", "nand"]


def layout_two_levels(inputs: list[str], first: Iterable[tuple[str, tuple[Atom, ...], GateType]],
                      second: Iterable[tuple[str, str, bool]], use_buffer: bool = True):
    pass