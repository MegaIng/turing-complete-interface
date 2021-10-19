from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from bitarray import bitarray

from turing_complete_interface.circuit_parser import Circuit, GateReference, GateShape, CircuitWire, CircuitPin
from turing_complete_interface.logic_nodes import CombinedLogicNode
from turing_complete_interface.tc_components import get_component, rev_components


@dataclass
class IOPosition:
    component_name: str
    pin_mapping: dict[str, str]
    force_id: str = None
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
                                  }, gate.id, gate.custom_data))
        return ios


@dataclass
class Space:
    x: int
    y: int
    w: int
    h: int
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
                if hasher is not None and hasher((x + self.x, y + self.y)) in self._protected:
                    continue
                for k in range(h):
                    if idx + k * self.w + w >= self.h:
                        continue
                    if self._taken_spaces[idx + k * self.w:idx + k * self.w + w].any():
                        continue
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
        return x + self.x, y + self.y


def build_circuit(node: CombinedLogicNode, io_positions: list[IOPosition], space: Space,
                  level_version: int = 0) -> Circuit:
    taken_ids: set[int] = set()
    i = 1

    def get_id() -> int:
        nonlocal i
        while i in taken_ids:
            i += 1
        taken_ids.add(i)
        return i

    def place(shape: GateShape, io: bool = True, forced_pos: tuple[int, int] = None):
        ox, oy, w, h = shape.bounding_box

        def translate(p):
            return (int((p[0] + 30 - ox) // 8 - 3), int((p[1] + 30 - oy) // 8 - 3))

        t, l = space.place(w, h, forced_pos, (translate if io else None))
        return t - ox, l - oy

    gate_refs = []
    pin_locations: dict[tuple[str | None, str], tuple[CircuitPin, int, int]] = {}
    for io in io_positions:
        shape, _ = get_component(io.component_name, io.custom_data)
        pos = place(shape, True)
        gi = get_id() if io.force_id is not None else io.force_id

        gate_refs.append(GateReference(io.component_name, pos, 0, str(gi), io.custom_data))

        for node_pin_name, shape_pin_name in io.pin_mapping.items():
            dp = shape.pins[shape_pin_name].pos
            pin_locations[None, node_pin_name] = shape.pins[shape_pin_name], pos[0] + dp[0], pos[1] + dp[1]

    for name, n in node.nodes.items():
        component_name, custom_data = rev_components[n.name]
        shape, _ = get_component(component_name, custom_data, no_node=True)
        pos = place(shape)
        gi = get_id()

        gate_refs.append(GateReference(component_name, pos, 0, str(gi), custom_data))

        for node_pin_name, pin in shape.pins.items():
            dp = pin.pos
            pin_locations[name, node_pin_name] = pin, pos[0] + dp[0], pos[1] + dp[1]

    wires = []

    for wire in node.wires:
        assert wire.source_bits == wire.target_bits, wire
        pin, *start = pin_locations[wire.source]
        _, *end = pin_locations[wire.target]
        wires.append(CircuitWire(len(wires) + 1, pin.is_byte, 0, "", (tuple(start), tuple(end))))
    return Circuit(gate_refs, wires, 99_999, 99_999, level_version)
