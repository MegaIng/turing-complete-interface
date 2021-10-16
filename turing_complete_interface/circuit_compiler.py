from collections import defaultdict
from dataclasses import dataclass
from frozendict import frozendict

from turing_complete_interface.tc_components import compute_gate_shape, get_component, spec_components
from .logic_nodes import LogicNodeType, Wire, OutputPin, InputPin, CombinedLogicNode, \
    build_or, CONST
from .circuit_parser import Circuit, GateReference, GateShape

Pos = tuple[int, int]


def build_connections(circuit: Circuit) -> dict[Pos, set[Pos]]:
    connections: defaultdict[Pos, set[Pos]] = defaultdict(set)
    for wire in circuit.wires:
        if len(wire.positions) > 1:
            a, b = connections[wire.positions[0]], connections[wire.positions[-1]]
            if a is b:
                continue
            assert a.isdisjoint(b)
            a.update({wire.positions[0], wire.positions[-1]})
            a.update(b)
            connections[wire.positions[-1]] = a
            for p in b:
                connections[p] = a
    return connections


@dataclass
class PinInfo:
    gate_ref: GateReference
    node_type: LogicNodeType
    gate_shape: GateShape
    name: str
    connection_name: str

    @property
    def is_io(self):
        return self.gate_shape.is_io

    @property
    def id(self):
        return str(self.gate_ref.id)

    @property
    def connector(self):
        return (None if self.is_io else self.id), self.connection_name

    @property
    def is_output(self):
        return self.name in self.node_type.outputs

    @property
    def is_input(self):
        return self.name in self.node_type.inputs

    @property
    def bits(self):
        return 8 if self.gate_shape.pins[self.name].is_bytes else 1

    @property
    def desc(self) -> InputPin | OutputPin:
        return self.node_type.inputs[self.name] if self.is_input else self.node_type.outputs[self.name]

    @property
    def summary(self):
        return f"<{self.node_type.name}: {self.id} {self.is_input=} {self.is_output=}>"


def build_connected_groups(circuit: Circuit) -> tuple[dict[str, LogicNodeType], list[list[PinInfo]], list[PinInfo],
                                                      dict[str, InputPin], dict[str, OutputPin]]:
    connections = {p: frozenset(ps) for p, ps in build_connections(circuit).items()}
    connected_groups: defaultdict[frozenset[Pos], list[PinInfo]] = defaultdict(list)
    nodes = {}
    missing_pins = []
    circuit_inputs = {}
    circuit_outputs = {}

    for gate in circuit.gates:
        shape, node = get_component(gate)
        assert set(node.inputs.keys()) | set(node.outputs.keys()) == set(map(str, shape.pins)), (
            set(node.inputs.keys()) | set(node.outputs.keys()), set(map(str, shape.pins)), node, shape)
        if not shape.is_io:
            nodes[str(gate.id)] = node
        for name, pin in shape.pins.items():
            p = gate.translate(pin.pos)
            if shape.is_io:
                if gate.name in {"Input1", "Input1B", "Output1", "Output1B"}:
                    pin_name = str(gate.id)
                else:
                    pin_name = f"{gate.id}.{name}"
                bit_size = 1 if not pin.is_bytes else 8
                if pin.is_input:  # This is a pin that takes an input to the outside of this circuit
                    # So this is an output of the circuit
                    circuit_outputs[pin_name] = OutputPin(bit_size)
                else:
                    circuit_inputs[pin_name] = InputPin(bit_size)
            else:
                pin_name = str(name)
            if p in connections:
                group = connections[p]
                connected_groups[group].append(PinInfo(gate, node, shape, str(name), pin_name))
            elif str(name) in node.inputs:
                missing_pins.append(PinInfo(gate, node, shape, str(name), pin_name))

    return nodes, list(connected_groups.values()), missing_pins, circuit_inputs, circuit_outputs


def build_gate(circuit_name: str, circuit: Circuit) -> CombinedLogicNode:
    wires: list[Wire] = []
    nodes, connected_groups, missing_pins, circuit_inputs, circuit_outputs = build_connected_groups(circuit)

    delayed_propagation = defaultdict(set)

    def wire(s, t, source_bits=None, target_bits=None):
        wires.append(Wire(s, t, source_bits, target_bits))
        (sn, sp), (tn, tp) = s, t
        if tn is None:  # This connects directly to an output, and therefore isn't delayed
            delayed_propagation[sn].add(None)
        elif nodes[tn].inputs[tp].delayed:  # This connects to a delayed output. Don't mark it
            return
        elif sn is None:
            delayed_propagation[None, sp].add(tn)
        else:
            delayed_propagation[sn].add(tn)

    for group in connected_groups:
        # The gates that act as inputs into the implicit Or gate, e.g. those with output pins into the gate
        input_gates = [p for p in group if p.is_output]
        if not input_gates:
            continue

        output_gates = [p for p in group if p.is_input]
        bit_size = input_gates[0].bits
        if len(input_gates) > 1:
            or_gate = build_or(*map(str, range(len(input_gates))), bit_size=bit_size)
            nodes[or_name := f"OR{len(nodes)}"] = or_gate
            for i, pin in enumerate(input_gates):
                source = pin.connector  # (str(pin.id) if not pin.is_io else None, pin.connection_name)
                if pin.bits != bit_size:
                    if pin.bits == 1:
                        nodes[pad_name := f"PAD{len(nodes)}"] = spec_components["TC_PADDER"]
                        wire(source, (pad_name, "single"))
                        source = (pad_name, "byte")
                    else:
                        nodes[any_name := f"DEPAD{len(nodes)}"] = spec_components["OR_1W8"]
                        wire(source, (any_name, "in"))
                        source = (any_name, "out")
                wire(source, (or_name, str(i)))
            source = or_name, "out"
        else:
            source = input_gates[0].connector

        for pin in output_gates:
            target = pin.connector
            if pin.bits != bit_size:
                if pin.bits == 1:
                    nodes[any_name := f"DEPAD{len(nodes)}"] = spec_components["OR_1W8"]
                    wire(source, (any_name, "in"))
                    current_source = (any_name, "out")
                else:
                    nodes[pad_name := f"PAD{len(nodes)}"] = spec_components["TC_PADDER"]
                    wire(source, (pad_name, "single"))
                    current_source = (pad_name, "byte")
            else:
                current_source = source
            wire(current_source, target)
    if missing_pins:
        nodes["_"] = CONST
        for pin in missing_pins:
            target = pin.connector
            if pin.bits != 1:
                for i in range(8):
                    wire(("_", "false"), target, target_bits=(i, i + 1))
            else:
                wire(("_", "false"), target)

    # Check which inputs are delayed

    new_inputs = {}
    for name, old in circuit_inputs.items():
        frontier = {(None, name)}
        seen = set()  # This should never be relevant, but just to make sure
        while frontier:
            node = frontier.pop()
            if node in seen:
                continue
            seen.add(node)
            follow = delayed_propagation.get(node, set())
            if None in follow:
                new_inputs[name] = InputPin(old.bits, False)
                break
            else:
                frontier.update(follow)
        else:
            new_inputs[name] = InputPin(old.bits, True)
    assert len(new_inputs) == len(circuit_inputs)

    shape = compute_gate_shape(circuit, circuit_name)
    for name, pin in new_inputs.items():
        shape.pins[name].is_bytes = pin.bits == 8
        shape.pins[name].is_delayed = pin.delayed
    return CombinedLogicNode(circuit_name, frozendict(nodes), frozendict(new_inputs), frozendict(circuit_outputs),
                             tuple(wires))
