from collections import defaultdict
from pathlib import Path

from bitarray import frozenbitarray
from bitarray.util import ba2int, int2ba
from frozendict import frozendict

from logic_nodes import LogicNodeType, Wire, DirectLogicNodeType, OutputPin, InputPin, NAND_2W1, CombinedLogicNode, \
    build_or, CONST
from circuit_parser import Circuit, GateReference, find_gate, GateShape
from specification_parser import load_all_components


def build_connections(circuit: Circuit) -> dict[tuple[int, int], set[tuple[int, int]]]:
    connections: defaultdict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
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


def build_gate(circuit_name: str, circuit: Circuit) -> CombinedLogicNode:
    connections = {p: frozenset(ps) for p, ps in build_connections(circuit).items()}
    wires: list[Wire] = []
    nodes: dict[str, LogicNodeType] = {}
    inputs: dict[str, InputPin] = {}
    outputs: dict[str, OutputPin] = {}
    connected_groups: defaultdict[frozenset[tuple[int, int]],
                                  list[tuple[GateReference, LogicNodeType, GateShape, str, str]]] = defaultdict(list)
    missing_pins = []
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
                    outputs[pin_name] = OutputPin(bit_size)
                else:
                    inputs[pin_name] = InputPin(bit_size)
            else:
                pin_name = str(name)
            if p in connections:
                group = connections[p]
                connected_groups[group].append((gate, node, shape, str(name), pin_name))
            elif str(name) in node.inputs:
                missing_pins.append((gate, node, shape, str(name), pin_name))

    for group in connected_groups.values():
        # The gates that act as inputs into the implicit Or gate, e.g. those with output pins into the gate
        input_gates = [t for t in group if t[3] not in t[1].inputs]
        if not input_gates:
            continue

        output_gates = [t for t in group if t[3] in t[1].inputs]
        bit_size = input_gates[0][1].outputs[input_gates[0][3]].bits
        if len(input_gates) > 1:
            or_gate = build_or(*map(str, range(len(input_gates))), bit_size=bit_size)
            nodes[or_name := f"OR{len(nodes)}"] = or_gate
            for i, pin in enumerate(input_gates):
                out = pin[1].outputs[pin[3]]
                source = (str(pin[0].id) if not pin[2].is_io else None, pin[4])
                if out.bits != bit_size:
                    if out.bits == 1:
                        nodes[pad_name := f"PAD{len(nodes)}"] = components["TC_PADDER"]
                        wires.append(Wire(source, (pad_name, "single")))
                        source = (pad_name, "byte")
                    else:
                        nodes[any_name := f"DEPAD{len(nodes)}"] = components["OR_1W8"]
                        wires.append(Wire(source, (any_name, "in")))
                        source = (any_name, "out")
                wires.append(Wire(source, (or_name, str(i))))
            source = or_name, "out"
        else:
            source = (str(input_gates[0][0].id) if not input_gates[0][2].is_io else None, input_gates[0][4])

        for pin in output_gates:
            target = (str(pin[0].id) if not pin[2].is_io else None), pin[4]
            out = pin[1].inputs[pin[3]]
            if out.bits != bit_size:
                if out.bits == 1:
                    nodes[any_name := f"DEPAD{len(nodes)}"] = components["OR_1W8"]
                    wires.append(Wire(source, (any_name, "in")))
                    current_source = (any_name, "out")
                else:
                    nodes[pad_name := f"PAD{len(nodes)}"] = components["TC_PADDER"]
                    wires.append(Wire(source, (pad_name, "single")))
                    current_source = (pad_name, "byte")
            else:
                current_source = source
            wires.append(Wire(current_source, target))
    if missing_pins:
        nodes["_"] = CONST
        for pin in missing_pins:
            inp = pin[1].inputs[pin[3]]
            target = (str(pin[0].id) if not pin[2].is_io else None), pin[4]
            if inp.bits != 1:
                for i in range(8):
                    wires.append(Wire(("_", "false"), target, target_bits=(i, i + 1)))
            else:
                wires.append(Wire(("_", "false"), target))

    return CombinedLogicNode(circuit_name, frozendict(nodes), frozendict(inputs), frozendict(outputs), tuple(wires))


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


def rom_func(*out_names):
    def f(args, state: frozenbitarray, delayed):
        address = ba2int(args["address"])
        ret = frozendict({
            name: state[(address + i) % 256 * 8:(address + 1) % 256 * 8 + 8]
            for i, name in enumerate(out_names)
        })
        return ret, state

    return f


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


def buffer(args, _):
    return frozendict({"out": args["in"]}), None


one = frozenbitarray("1")
zero = frozenbitarray("0")


def mul_func(args, _, _1):
    a = ba2int(args["a"], signed=False)
    b = ba2int(args["b"], signed=False)
    return frozendict({"out": int2ba((a * b) % 256, 8, "little")}), None


def less_func(args, _):
    au, as_ = ba2int(args["a"], signed=False), ba2int(args["a"], signed=True)
    bu, bs = ba2int(args["b"], signed=False), ba2int(args["b"], signed=True)
    return frozendict({
        "unsigned": one if au < bu else zero,
        "signed": one if as_ < bs else zero
    }), None


components = load_all_components((Path("components")))
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
        "b": OutputPin(1)}
    ), 0, error),
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
    "Counter": components["COUNTER_8"].renamed({
        "save": "overwrite",
        "in": "in_value",
        "out": "out_value",
    }),

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
    "Screen": DirectLogicNodeType("Screen", frozendict({
    }), frozendict({
    }), 0, lambda *_: (frozendict(), None)),

    "Program": DirectLogicNodeType("Program", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out": OutputPin(8),
    }), 8 * (2 ** 8), rom_func("out")),
    "Program2": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
    }), 8 * (2 ** 8), rom_func("out0", "out1")),
    "Program3": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
        "out2": OutputPin(8),
    }), 8 * (2 ** 8), rom_func("out0", "out1", "out2")),
    "Program4": DirectLogicNodeType("Program4", frozendict({
        "address": InputPin(8),
    }), frozendict({
        "out0": OutputPin(8),
        "out1": OutputPin(8),
        "out2": OutputPin(8),
        "out3": OutputPin(8),
    }), 8 * (2 ** 8), rom_func("out0", "out1", "out2", "out3")),
    "ByteConstant": byte_constant
}

compiled_custom = {}


def get_node(gate: str | GateReference) -> LogicNodeType:
    if isinstance(gate, GateReference):
        if gate.name == "Custom":
            if gate.custom_data not in compiled_custom:
                compiled_custom[gate.custom_data] = build_gate(gate.custom_data, find_gate(gate)[0])
            return compiled_custom[gate.custom_data]
        print(gate)
        gate_name = gate.name
    else:
        gate_name = gate
    n = builtin_components[gate_name]
    if callable(n):
        return n(gate)
    else:
        return n
