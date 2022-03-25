import json
from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

from bitarray import bitarray, frozenbitarray
from bitarray.util import int2ba, ba2int
from frozendict import frozendict

from .circuit_parser import GateShape, GateReference, SPECIAL_RED, NORMAL, CircuitPin, BigShape, SCHEMATICS_PATH, \
    CUSTOM, \
    Circuit, SPECIAL_GREEN
from .logic_nodes import LogicNodeType, DirectLogicNodeType, InputPin, OutputPin, build_or as ln_build_or, \
    builtins_gates, CombinedLogicNode, Wire
from .specification_parser import load_all_components, spec_components


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


def byte_constant(_, raw_value):
    i_value = 0 if not raw_value else int(raw_value)
    value = frozenbitarray(int2ba(i_value, 8, endian="little"), )
    res = frozendict({"out": value})

    def f(*args):
        return res, None

    return DirectLogicNodeType(f"Constant{i_value}", frozendict(), frozendict({
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


def build_counter(gate_name, custom_data):
    delta = int(custom_data)

    return CombinedLogicNode(
        f"Counter{delta}", frozendict({
            "counter": spec_components["VARCOUNTER_8"],
            "delta": byte_constant("", delta)
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
    "IO": SPECIAL_RED,
    "special": SPECIAL_RED,
    "special_green": SPECIAL_GREEN,
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
    node_to_component: dict[str, tuple[str, str]] = {}
    for category, raw in data.items():
        assert category in category_colors, category
        color = category_colors[category]
        for name, d in raw.items():
            shape = GateShape(
                name,
                color,
                {
                    str(pn): CircuitPin(pd["pos"], pd["type"] == "input", pd["size"] == "byte", pd.get("is_delayed", False), pn)
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
            if isinstance(node, LogicNodeType):
                assert node.name not in node_to_component, f"Non unique node name {node.name}"
                node_to_component[node.name] = name, ""
    return components, node_to_component


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
                if gate.custom_data:
                    cc_pin_name = gate.custom_data.partition(':')[-1]
                else:
                    cc_pin_name = out_pin
                pins[str(out_pin)] = CircuitPin(p, not pin.is_input, pin.is_byte, name=cc_pin_name)
    circuit.shape = GateShape(name, CUSTOM, pins, list(blocks), text=lambda _: name)
    return circuit.shape


@dataclass
class _CustomComponentRef:
    path: Path
    circuit: Circuit
    shape: GateShape = None
    node: LogicNodeType = None

    def get(self, no_node: bool = False):
        if self.shape is None:
            self.shape = compute_gate_shape(self.circuit, f"Custom_{self.path.name}")
        if self.node is None and not no_node:
            from .circuit_compiler import build_gate
            self.node = build_gate(f"Custom_{self.path.name}", self.circuit)
            if self.node.name in rev_components:
                raise ValueError(f"Non unique node name {self.node.name} (for Custom component {self.path.name})")
            rev_components[self.node.name] = ("Custom", self.id)
        return self.shape, self.node

    @property
    def id(self) -> int:
        return self.circuit.save_version

    @property
    def name(self):
        return self.path.name


def load_custom():
    global cc_by_path, cc_by_id
    base = SCHEMATICS_PATH / "component_factory"
    for path in Path(base).rglob("circuit.data"):
        try:
            circuit = Circuit.parse(path.read_bytes())
            # Don't compile immediately. Wait if we are asked
            ref = _CustomComponentRef(path.relative_to(base).parent, circuit)
            cc_by_id[circuit.save_version] = ref
            cc_by_path[str(path.relative_to(base).parent)] = ref
        except Exception as e:
            print(type(e), e)


std_components: dict[str, tuple[GateShape, LogicNodeType]]
rev_components: dict[str, tuple[str, str | int]]
std_components, rev_components = load_components()
cc_by_path: dict[str, _CustomComponentRef] = {}
cc_by_id: dict[int, _CustomComponentRef] = {}
if SCHEMATICS_PATH is not None:
    load_custom()


def get_custom_component(custom_data: str | int, no_node: bool = False):
    try:
        ref = cc_by_id[int(custom_data)]
    except (ValueError, KeyError):
        ref = cc_by_path[custom_data]
    ref.get(no_node)
    return ref


def get_component(gate_name: str | GateReference, custom_data: str | int = None, no_node: bool = False) \
        -> tuple[GateShape, LogicNodeType | None]:
    if isinstance(gate_name, GateReference):
        custom_data = gate_name.custom_id if gate_name.name == "Custom" else gate_name.custom_data
        gate_name = gate_name.name
    if gate_name == "Custom":
        return get_custom_component(custom_data, no_node).get(no_node)
    s, n = std_components[gate_name]
    if callable(n):
        if not no_node:
            n = n(gate_name, custom_data)
            if n.name in rev_components:
                prev = rev_components[n.name]
                if prev[0] != gate_name:
                    assert False, f"Non unique name {n.name} for {(gate_name, custom_data)} (previous: {prev})"
                if prev[1] != custom_data and {prev[1], custom_data} != {"", "0"}:
                    assert False, f"Non unique name {n.name} for {(gate_name, custom_data)} (previous: {prev})"
            else:
                rev_components[n.name] = gate_name, custom_data
        else:
            n = None
        return s, n
    else:
        return s, n
