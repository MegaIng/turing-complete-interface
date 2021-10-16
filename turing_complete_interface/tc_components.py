import json
from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

from bitarray import bitarray, frozenbitarray
from bitarray.util import int2ba, ba2int
from frozendict import frozendict

from .circuit_parser import GateShape, GateReference, SPECIAL, NORMAL, CircuitPin, BigShape, SCHEMATICS_PATH, CUSTOM, \
    Circuit
from .logic_nodes import LogicNodeType, DirectLogicNodeType, InputPin, OutputPin, build_or as ln_build_or, \
    builtins_gates, CombinedLogicNode, Wire
from .specification_parser import load_all_components


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


program = bitarray([0] * 8 * (2 ** 8), endian="little")


def build_rom(shape: GateShape, data):
    def f(args, state: frozenbitarray, delayed):
        address = ba2int(args["address"])
        ret = frozendict({
            name: program[(address + i) % 256 * 8:(address + i) % 256 * 8 + 8]
            for i, name in enumerate(out_names)
        })
        print(args, address, len(program), ret)
        return ret, state

    out_names = [name for name, p in shape.pins.items() if not p.is_input]
    return DirectLogicNodeType(
        shape.name, frozendict({
            "address": InputPin(8)
        }), frozendict({
            name: OutputPin(8) for name in out_names
        }), 0, f
    )


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


def byte_constant(gate_or_value):
    if isinstance(gate_or_value, GateReference):
        value = 0 if not gate_or_value.custom_data else int(gate_or_value.custom_data)
    else:
        value = int(gate_or_value)
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

    return CombinedLogicNode(
        f"Counter{delta}", frozendict({
            "counter": spec_components["VARCOUNTER_8"],
            "delta": byte_constant(delta)
        }), frozendict({
            "in": InputPin(8, True),
            "overwrite": InputPin(1, True),
        }), frozendict({
            "out": OutputPin(8)
        }), (
            Wire((None, "in"), ("counter", "in")),
            Wire((None, "overwrite"), ("counter", "save")),
            Wire(("delta", "out"), ("counter", "delta")),
            Wire(("counter", "out"), (None, "out"))
        ))


category_colors = {
    "IO": SPECIAL,
    "special": SPECIAL,
    "normal": NORMAL,
}

text_functions = {
    "ByteConstant": lambda gate: str(gate.custom_data or 0),
    "Program1": lambda gate: gate.name,
    "Program2": lambda gate: gate.name,
    "Program3": lambda gate: gate.name,
    "Program4": lambda gate: gate.name,
}


def build_or(shape: GateShape, data):
    is_byte = None
    ins = []
    out = None
    for n, p in shape.pins.items():
        if is_byte is None:
            is_byte = p.is_byte
        else:
            assert is_byte == p.is_byte
        if p.is_input:
            ins.append(n)
        else:
            assert out is None
            out = n
    return ln_build_or(*ins, bit_size=[0, 8][is_byte], out_name=out)


def noop(*_):
    return frozendict(), None


def load_components():
    with Path(__file__).with_name("tc_components.json").open() as f:
        data = json.load(f)

    components: dict[str, tuple[GateShape, LogicNodeType | Callable[[GateReference], LogicNodeType]]] = {}
    for category, raw in data.items():
        assert category in category_colors, category
        color = category_colors[category]
        for name, d in raw.items():
            shape = GateShape(
                name,
                color,
                {
                    pn: CircuitPin(pd["pos"], pd["type"] == "input", pd["size"] == "byte", pd.get("is_delayed", False))
                    for pn, pd in d["pins"].items()
                },
                d["blocks"],
                category == "IO",
                text_functions.get(name, lambda gate: str(gate.custom_data or gate.name)),
                (BigShape(*d["big_shape"]) if "big_shape" in d else None)
            )
            if d["type"] == "generate":
                node = eval(d["func"])
            elif d["type"] in ("direct", "error", "virtual"):
                node = DirectLogicNodeType(
                    name, frozendict({
                        pn: InputPin((1, 8)[cp.is_byte], cp.is_delayed)
                        for pn, cp in shape.pins.items() if cp.is_input
                    }), frozendict({
                        pn: OutputPin((1, 8)[cp.is_byte])
                        for pn, cp in shape.pins.items() if not cp.is_input
                    }), d["state_size"], eval(d.get("func", "error")))
            elif d["type"] == "build":
                node = eval(d["func"])(shape, d)
            elif d["type"] == "builtin":
                node = builtins_gates[d["builtin_name"]]
            elif d["type"] == "combined":
                node = spec_components[d["spec"]]
            else:
                assert False, d["type"]
            components[name] = shape, node
    return components


def compute_gate_shape(circuit, name: str) -> GateShape:
    if circuit.shape is not None:
        if circuit.shape.name is None:
            circuit.shape.name = name
        assert name is None or circuit.shape.name == name, (circuit.shape.name, name)
        return circuit.shape

    def translate(p):
        return (int((p[0] + 30) // 8 - 3), int((p[1] + 30) // 8 - 3))

    blocks = set()
    for gate in circuit.gates:
        blocks.add(translate(gate.pos))
    pins = {}
    for gate in circuit.gates:
        if gate.name in std_components and ((io_shape := std_components[gate.name][0]).is_io):
            p = translate(gate.pos)
            if p in blocks:
                blocks.remove(p)
            for pin_name, pin in io_shape.pins.items():
                if len(io_shape.pins) > 1:
                    out_pin = f"{gate.id}.{pin_name}"
                else:
                    out_pin = gate.id
                pins[out_pin] = CircuitPin(p, pin.is_input, pin.is_byte)
    circuit.shape = GateShape(name, CUSTOM, pins, list(blocks))
    return circuit.shape


def load_custom():
    res = {}
    for path in Path(SCHEMATICS_PATH / "component_factory").iterdir():
        circuit = Circuit.parse((path / "circuit.data").read_text())
        # Don't compile immediately. Wait if we are asked
        res[path.name] = circuit, None, None
    return res


spec_components = load_all_components(Path())
std_components: dict[str, tuple[GateShape, LogicNodeType]] = load_components()
custom_components: dict[str, tuple[Circuit, GateShape | None, LogicNodeType | None]] = load_custom()


def get_component(gate: str | GateReference) -> tuple[GateShape, LogicNodeType]:
    if isinstance(gate, GateReference):
        if gate.name == "Custom":
            assert gate.custom_data in custom_components
            circuit, shape, node = custom_components[gate.custom_data]
            if shape is None:
                from .circuit_compiler import build_gate
                shape = compute_gate_shape(circuit, gate.name)
                node = build_gate(gate.name, circuit)
                custom_components[gate.custom_data] = circuit, shape, node
            return custom_components[gate.custom_data][1:]
        gate_name = gate.name
    else:
        gate_name = gate
    s, n = std_components[gate_name]
    if callable(n):
        return s, n(gate)
    else:
        return s, n
