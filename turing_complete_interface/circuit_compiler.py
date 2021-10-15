from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from bitarray import frozenbitarray, bitarray
from bitarray.util import ba2int, int2ba
from frozendict import frozendict

from .logic_nodes import LogicNodeType, Wire, DirectLogicNodeType, OutputPin, InputPin, NAND_2W1, CombinedLogicNode, \
    build_or, CONST
from .circuit_parser import Circuit, GateReference, find_gate, GateShape
from .specification_parser import load_all_components

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
        _, shape = find_gate(gate)
        node = get_node(gate)
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
                        nodes[pad_name := f"PAD{len(nodes)}"] = components["TC_PADDER"]
                        wire(source, (pad_name, "single"))
                        source = (pad_name, "byte")
                    else:
                        nodes[any_name := f"DEPAD{len(nodes)}"] = components["OR_1W8"]
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
                    nodes[any_name := f"DEPAD{len(nodes)}"] = components["OR_1W8"]
                    wire(source, (any_name, "in"))
                    current_source = (any_name, "out")
                else:
                    nodes[pad_name := f"PAD{len(nodes)}"] = components["TC_PADDER"]
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

    shape = circuit.compute_gate_shape(circuit_name)
    for name, pin in new_inputs.items():
        shape.pins[name].is_bytes = pin.bits == 8
        shape.pins[name].is_delayed = pin.delayed
    return CombinedLogicNode(circuit_name, frozendict(nodes), frozendict(new_inputs), frozendict(circuit_outputs),
                             tuple(wires))


def ram_func(args, state: frozenbitarray, delayed):
    address = ba2int(args["address"])
    if args["load"].any():
        ret = frozendict({
            "value_out": state[address * 8:address * 8 + 8]
        })
    else:
        ret = frozendict({
            "value_out": frozenbitarray((0,) * 8)
        })
    if args["save"].any() and delayed:
        new_state = state[:address * 8] + args["value_in"] + state[address * 8 + 8:]
    else:
        new_state = state
    return ret, new_state


program = bitarray([0] * (2 ** 8), endian="little")


def rom_func(*out_names):
    def f(args, state: frozenbitarray, delayed):
        address = ba2int(args["address"])
        ret = frozendict({
            name: program[(address + i) % 256 * 8:(address + i) % 256 * 8 + 8]
            for i, name in enumerate(out_names)
        })
        return ret, state

    return f


screens = {}


@dataclass
class AsciiScreen:
    background_color: tuple[int, int, int]
    ascii_screen: bytearray = field(default_factory=lambda: bytearray([0] * 18 * 14 * 2))
    ascii_screen_buffer: bytearray = field(default_factory=lambda: bytearray([0] * 18 * 14 * 2))
    ascii_cursor: int = 0

    def func(self, args, state: frozenbitarray, delayed):
        if not delayed:
            return frozendict(), state
        if args["write_cursor"].any():
            match ba2int(args["cursor"]):
                case 252:
                    state = ~state
                case 253:
                    self.ascii_screen, self.ascii_screen_buffer = self.ascii_screen_buffer, self.ascii_screen
                case 254:
                    self.ascii_screen[:] = (0,) * len(self.ascii_screen)
                case 255:
                    pass
                case v:
                    self.ascii_cursor = v
        buffered = state[0]
        target = self.ascii_screen_buffer if buffered else self.ascii_screen
        if args["write_color"].any():
            target[self.ascii_cursor * 2] = ba2int(args["color"])
        if args["write_char"].any():
            target[self.ascii_cursor * 2 + 1] = ba2int(args["char"])
        return frozendict(), state


def build_ascii(gate):
    if gate.id not in screens:
        c = gate.custom_data
        screens[gate.id] = AsciiScreen((0, 0, 0) if not c else (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)))
    screen = screens[gate.id]
    return DirectLogicNodeType("AsciiScreen", frozendict({
        "write_cursor": InputPin(1, True),
        "cursor": InputPin(8, True),
        "write_color": InputPin(1, True),
        "color": InputPin(8, True),
        "write_char": InputPin(1, True),
        "char": InputPin(8, True),
    }), frozendict(), 1, screen.func)


def stack_func(args, state: frozenbitarray, delayed):
    assert len(state[-8:]) == 8
    address = ba2int(state[-8:])
    if args["load"].any():
        address -= 1
        address %= 256
        ret = frozendict({
            "value_out": state[address * 8:address * 8 + 8]
        })
    else:
        ret = frozendict({
            "value_out": frozenbitarray((0,) * 8)
        })
    if args["save"].any():
        new_state = state[:address * 8] + args["value_in"] + state[address * 8 + 8:]
        address += 1
        address %= 256
    else:
        new_state = state
    if delayed:
        new_state = new_state[:-8] + frozenbitarray(int2ba(address, 8, endian="little"))
    else:
        new_state = state
    return ret, new_state


def error(*args):
    raise ValueError("Can't execute this node")


def byte_constant(gate):
    assert isinstance(gate, GateReference), gate
    value = 0 if not gate.custom_data else int(gate.custom_data)
    value = frozenbitarray(int2ba(value, 8, endian="little"), )
    res = frozendict({"out": value})

    def f(*args):
        return res, None

    return DirectLogicNodeType("Constant", frozendict(), frozendict({
        "out": OutputPin(8)
    }), 0, f)


def buffer(args, *_):
    return frozendict({"out": args["in"]}), None


last_key: int = 0


def keyboard(args, _, _1):
    if args["enable"].any():
        key = last_key
    else:
        key = 0
    print(key)
    return frozendict({"out": frozenbitarray(int2ba(key, 8, "little"))}), None


one = frozenbitarray("1")
zero = frozenbitarray("0")


def mul_func(args, _, _1):
    a = ba2int(args["a"], signed=False)
    b = ba2int(args["b"], signed=False)
    return frozendict({"out": int2ba((a * b) % 256, 8, "little")}), None


def less_func(args, _, _1):
    au, as_ = ba2int(args["a"], signed=False), ba2int(args["a"], signed=True)
    bu, bs = ba2int(args["b"], signed=False), ba2int(args["b"], signed=True)
    return frozendict({
        "unsigned": one if au < bu else zero,
        "signed": one if as_ < bs else zero
    }), None


def build_counter(gate):
    delta = int(gate.custom_data)

    def counter_func(args, state: frozenbitarray, delayed):
        if delayed:
            if args["overwrite"].any():
                new_state = args["in"]
            else:
                new_state = int2ba(ba2int(state) + delta, 8, endian="little")
        else:
            new_state = state
        return frozendict({
            "out": state
        }), new_state

    return DirectLogicNodeType("Counter", frozendict({
        "in": InputPin(8, True),
        "overwrite": InputPin(1, True),
    }), frozendict({
        "out": OutputPin(8)
    }), 8, counter_func)


components = load_all_components((Path(__file__).parent / "components"))
builtin_components = {
    "Input1": DirectLogicNodeType("Input1", frozendict(), frozendict({
        "value": OutputPin(1)
    }), 0, error),
    "Input1B": DirectLogicNodeType("Input1B", frozendict(), frozendict({
        "value": OutputPin(8)
    }), 0, error),
    "Input1_1B": DirectLogicNodeType("Input1_1B", frozendict({
        "control": InputPin(1)
    }), frozendict({
        "value": OutputPin(8),
    }), 0, error),
    "Input1BConditions": DirectLogicNodeType("Input1BConditions", frozendict(), frozendict({
        "value": OutputPin(8)
    }), 0, error),
    "Input2": DirectLogicNodeType("Input2", frozendict(), frozendict({
        "a": OutputPin(1),
        "b": OutputPin(1)}), 0, error),
    "Input3": DirectLogicNodeType("Input3", frozendict(), frozendict({
        "a": OutputPin(1),
        "b": OutputPin(1),
        "c": OutputPin(1),
    }), 0, error),
    "Input4": DirectLogicNodeType("Input4", frozendict(), frozendict({
        "a": OutputPin(1),
        "b": OutputPin(1),
        "c": OutputPin(1),
        "d": OutputPin(1),
    }), 0, error),
    "Output1": DirectLogicNodeType("Output1", frozendict({
        "value": InputPin(1, False)
    }), frozendict(), 0, error),
    "Output1B": DirectLogicNodeType("Output1N", frozendict({
        "value": InputPin(8, False)
    }), frozendict(), 0, error),
    "Output1_1B": DirectLogicNodeType("Output1_1B", frozendict({
        "control": InputPin(1, False),
        "value": InputPin(8, False),
    }), frozendict(), 0, error),
    "Output1Sum": DirectLogicNodeType("Output1Sum", frozendict({
        "value": InputPin(1, False)
    }), frozendict(), 0, error),
    "Output1Car": DirectLogicNodeType("Output1Car", frozendict({
        "value": InputPin(1, False)
    }), frozendict(), 0, error),
    "OutputCounter": DirectLogicNodeType("OutputCounter", frozendict({
        "a": InputPin(1, False),
        "b": InputPin(1, False),
        "c": InputPin(1, False),
    }), frozendict(), 0, error),
    "Output4": DirectLogicNodeType("Output4", frozendict({
        "a": InputPin(1, False),
        "b": InputPin(1, False),
        "c": InputPin(1, False),
        "d": InputPin(1, False),
    }), frozendict(), 0, error),

    "Buffer": DirectLogicNodeType("Buffer", frozendict({
        "in": InputPin(1, False)
    }), frozendict({
        "out": OutputPin(1)
    }), 0, buffer),

    "BiggerDemux": components["TC_DEMUX_3"].renamed({
        "1_a": "a",
        "1_b": "b",
        "1_c": "c",
        "2_a": "r0",
        "2_b": "r1",
        "2_c": "r2",
        "2_d": "r3",
        "3_a": "r4",
        "3_b": "r5",
        "3_c": "r6",
        "3_d": "r7",
    }),
    "Nand": NAND_2W1,
    "Not": components["NOT_1W1"],
    "Or": build_or("a", "b"),
    "Or3": build_or("a", "b", "c"),
    "Nor": components["NOR_2W1"],
    "And": components["AND_2W1"],
    "And3": components["AND_3W1"],
    "Xor": components["XOR_2W1"],
    "Xnor": components["XNOR_2W1"],
    "Demux": components["TC_DEMUX_2"],
    "Register": components["TC_REGISTER_8"],
    "ByteAdd": components["TC_PARTIAL_ADDER_8"],
    "ByteAdd2": components["ADDER_2W8"],
    "ByteSwitch": components["SWITCH_1W8"],
    "ByteSplitter": components["TC_BYTE_SPLITTER"],
    "ByteMaker": components["TC_BYTE_MAKER"],
    "ByteNot": components["NOT_1W8"],
    "ByteOr": build_or("a", "b", bit_size=8),
    "ByteXor": components["XOR_2W8"],
    "ByteMul": DirectLogicNodeType("ByteMul", frozendict({
        "a": InputPin(8, False),
        "b": InputPin(8, False),
    }), frozendict({
        "out": OutputPin(8),
    }), 0, mul_func),
    "ByteLess": DirectLogicNodeType("ByteLess", frozendict({
        "a": InputPin(8, False),
        "b": InputPin(8, False),
    }), frozendict({
        "unsigned": OutputPin(1),
        "signed": OutputPin(1),
    }), 0, less_func),
    "ByteEqual": components["TC_BYTE_EQUAL"].renamed({
        "1": "a",
        "2": "b",
        "3": "out"
    }),
    "On": CONST,
    "Mux": components["MUX_2W8"],
    "Counter": build_counter,

    "Ram": DirectLogicNodeType("Ram", frozendict({
        "load": InputPin(1),
        "save": InputPin(1),
        "address": InputPin(8),
        "value_in": InputPin(8, True),
    }), frozendict({
        "value_out": OutputPin(8),
    }), 8 * (2 ** 8), ram_func),

    "Stack": DirectLogicNodeType("Stack", frozendict({
        "load": InputPin(1),
        "save": InputPin(1),
        "value_in": InputPin(8, True),
    }), frozendict({
        "value_out": OutputPin(8),
    }), 8 * (2 ** 8) + 8, stack_func),
    "Screen": DirectLogicNodeType("Screen", frozendict(), frozendict(), 0, lambda *_: (frozendict(), None)),
    "Keyboard": DirectLogicNodeType("Keyboard", frozendict({
        "enable": InputPin(1, False)
    }), frozendict({
        "out": OutputPin(8)
    }), 0, keyboard),
    "AsciiScreen": build_ascii,

    "Program1": DirectLogicNodeType("Program1", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out": OutputPin(8),
    }), 0, rom_func("out")),
    "Program2": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
    }), 0, rom_func("out0", "out1")),
    "Program3": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
        "out2": OutputPin(8),
    }), 0, rom_func("out0", "out1", "out2")),
    "Program4": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
        "out2": OutputPin(8),
        "out3": OutputPin(8),
    }), 0, rom_func("out0", "out1", "out2", "out3")),
    "ByteConstant": byte_constant
}

compiled_custom = {}


def get_node(gate: str | GateReference) -> LogicNodeType:
    if isinstance(gate, GateReference):
        if gate.name == "Custom":
            if gate.custom_data not in compiled_custom:
                compiled_custom[gate.custom_data] = build_gate(gate.custom_data, find_gate(gate)[0])
            return compiled_custom[gate.custom_data]
        gate_name = gate.name
    else:
        gate_name = gate
    n = builtin_components[gate_name]
    if callable(n):
        return n(gate)
    else:
        return n
