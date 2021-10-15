from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Callable

OR_NO_DATA = """\
1|Input2`-10`3`0`1`;Output1`-4`3`0`2`;Nand`-4`-3`0`3`|3`0`10``-7,3,-6,3,-5,3;2`0`10``-10,4,-9,4,-8,4,-7,3;1`0`10``-10,2,-9,2,-8,2,-7,3|1,0"""


# GRAMMAR = """
# start: preamble "|" gates "|" wires "|" conclusion
#
# preamble: INT
# conclusion: INT "," INT
#
# UNKNOWN: /[^|]+/
#
# gates: (gate (";" gate)*)?
#
# gate: NAME _SEP x _SEP y _SEP rot _SEP id _SEP
#
# wires: (wire (";" wire)*)?
#
# wire:  INT
#
# _SEP: "`"
#
# %import common.SIGNED_INTEGER -> INT
# """

def pre_parse(text: str) -> list[list[list[list[str]]]]:
    return [[
        [
            part.split(",") if "," in part else part
            for part in element.split("`")
        ] for element in section.split(";")
    ] for section in text.split("|")]


@dataclass
class GateReference:
    name: str
    pos: tuple[int, int]
    rotation: int
    id: int
    custom_data: str

    @classmethod
    def parse(cls, values) -> GateReference:
        name, x, y, r, i, custom_data = (v for v in values)
        return GateReference(
            name, (int(x), int(y)), int(r), i, custom_data
        )

    def translate(self, dp: tuple[int, int]):
        dp = self.rot(dp)
        return self.pos[0] + dp[0], self.pos[1] + dp[1]

    def rot(self, dp: tuple[int, int]):
        (a, b), (c, d) = [
            ((1, 0), (0, 1)),
            ((0, -1), (1, 0)),
            ((-1, 0), (0, -1)),
            ((0, 1), (-1, 0)),
        ][self.rotation]
        return a * dp[0] + b * dp[1], c * dp[0] + d * dp[1]


@dataclass
class CircuitWire:
    id: int
    is_byte: bool
    color: int
    label: str
    positions: list[tuple[int, int]]

    @classmethod
    def parse(cls, values) -> CircuitWire:
        i, is_byte, color, label, positions = values
        assert is_byte in ("0", "1")
        return CircuitWire(int(i), is_byte == "1", int(color), label,
                           [(int(x), int(y)) for x, y in zip(positions[::2], positions[1::2])])


@dataclass
class Circuit:
    gates: list[GateReference]
    wires: list[CircuitWire]
    nand_cost: int
    delay: int
    shape: GateShape = None

    @property
    def score(self):
        return self.nand_cost + self.delay

    @classmethod
    def parse(cls, text: str) -> Circuit:
        version, raw_gates, raw_wires, score, *level_version = pre_parse(text)
        match score:
            case ((nand_cost, delay), ):
                nand_cost = int(nand_cost)
                delay = int(delay)
            case _:
                nand_cost = delay = 0
        assert version == [["1"]], version
        return Circuit([GateReference.parse(d) for d in raw_gates],
                       [CircuitWire.parse(d) for d in raw_wires if d != ['']],
                       int(nand_cost), int(delay))

    def compute_gate_shape(self, name: str) -> GateShape:
        if self.shape is not None:
            if self.shape.name is None:
                self.shape.name = name
            assert name is None or self.shape.name == name, (self.shape.name, name)
            return self.shape

        def translate(p):
            return (int((p[0] + 30) // 8 - 3), int((p[1] + 30) // 8 - 3))

        blocks = set()
        for gate in self.gates:
            blocks.add(translate(gate.pos))
        pins = {}
        for gate in self.gates:
            if gate.name in DEFAULT_GATES and DEFAULT_GATES[gate.name].is_io:
                p = translate(gate.pos)
                if p in blocks:
                    blocks.remove(p)
                pins[gate.id] = CircuitPin(p, "Input" in DEFAULT_GATES[gate.name].name, )
        self.shape = GateShape(name, CUSTOM, pins, list(blocks))
        return self.shape


@dataclass
class BigShape:
    tl: tuple[int, int]
    size: tuple[int, int]


@dataclass
class CircuitPin:
    pos: tuple[int, int]
    is_input: bool
    is_bytes: bool = False
    is_delayed: bool = False


@dataclass
class GateShape:
    name: str
    color: tuple[int, int, int]
    pins: dict[str | int, CircuitPin]
    blocks: list[tuple[int, int]]
    is_io: bool = False
    text: Callable[[GateReference], str] = staticmethod(lambda gate: str(gate.custom_data or gate.name))
    big_shape: BigShape = None


SPECIAL = (206, 89, 107)
NORMAL = (28, 95, 147)
CUSTOM = (30, 165, 174)

DEFAULT_GATES: dict[str, GateShape] = {
    "Input1": GateShape("Input1", SPECIAL, {
        "value": CircuitPin((1, 0), False)
    }, [(0, 0), (0, -1), (0, 1)], True),
    "Input2": GateShape("Input2", SPECIAL, {
        "a": CircuitPin((0, 1), False),
        "b": CircuitPin((0, -1), False)
    }, [(-1, 1), (-1, 0), (-1, -1), (0, 0)], True),
    "Input3": GateShape("Input4", SPECIAL, {
        "a": CircuitPin((1, -2), False),
        "b": CircuitPin((1, -1), False),
        "c": CircuitPin((1, 0), False),
    }, [(0, -2), (0, -1), (0, 0)], True),
    "Input4": GateShape("Input4", SPECIAL, {
        "a": CircuitPin((1, -2), False),
        "b": CircuitPin((1, -1), False),
        "c": CircuitPin((1, 0), False),
        "d": CircuitPin((1, 1), False)
    }, [(0, -2), (0, -1), (0, 0), (0, 1)], True),
    "Input1B": GateShape("Input1B", SPECIAL, {
        "value": CircuitPin((1, 0), False, True)
    }, [(0, 0), (0, -1)], True),
    "Input1BConditions": GateShape("Input1BConditions", SPECIAL, {
        "value": CircuitPin((1, 0), False, True)
    }, [(0, 0), (0, -1)], True),
    "Input1_1B": GateShape("Output1_1B", SPECIAL, {
        "value": CircuitPin((1, 0), False, True), "control": CircuitPin((0, 1), False)
    }, [(0, 0), (0, -1)], True),

    "Output1": GateShape("Output1", SPECIAL, {
        "value": CircuitPin((-1, 0), True)
    }, [(0, 0), (0, 1), (0, -1)], True),
    "Output1B": GateShape("Output1B", SPECIAL, {
        "value": CircuitPin((-1, 0), True, is_bytes=True)
    }, [(0, 0), (0, 1), (0, -1)], True),
    "Output1_1B": GateShape("Output1_1B", SPECIAL, {
        "value": CircuitPin((-1, 0), True),
        "control": CircuitPin((0, 1), True)
    }, [(0, 0), (0, -1)], True),
    "Output1Car": GateShape("Output1Car", SPECIAL, {
        "value": CircuitPin((-1, 0), True)
    }, [(0, 0), (0, 1), (0, -1)], True),
    "Output1Sum": GateShape("Output1Sum", SPECIAL, {
        "value": CircuitPin((-1, 0), True)
    }, [(0, 0), (0, 1), (0, -1)], True),
    "OutputCounter": GateShape("OutputCounter", SPECIAL, {
        "a": CircuitPin((-1, -1), True),
        "b": CircuitPin((-1, 0), True),
        "c": CircuitPin((-1, 1), True)
    }, [(0, 0), (0, 1), (0, -1)], True),
    "Output4": GateShape("Output4", SPECIAL, {
        "a": CircuitPin((-1, -2), True),
        "b": CircuitPin((-1, -1), True),
        "c": CircuitPin((-1, 0), True),
        "d": CircuitPin((-1, 1), True)
    }, [(0, 0), (0, 1), (0, 2), (0, -1)], True),

    "Nand": GateShape("Nand", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "And": GateShape("And", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Or": GateShape("Or", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Nor": GateShape("Nor", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Xor": GateShape("Xor", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Xnor": GateShape("Xnor", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Or3": GateShape("Or3", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, 0), True),
        "c": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "And3": GateShape("And3", NORMAL, {
        "a": CircuitPin((-1, 1), True),
        "b": CircuitPin((-1, 0), True),
        "c": CircuitPin((-1, -1), True),
        "out": CircuitPin((2, 0), False)
    }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
    "Not": GateShape("Not", NORMAL, {
        "in": CircuitPin((-1, 0), True),
        "out": CircuitPin((1, 0), False)
    }, [(0, 0)]),
    "Buffer": GateShape("Buffer", NORMAL, {
        "in": CircuitPin((-1, 0), True),
        "out": CircuitPin((1, 0), False)
    }, [(0, 0)]),
    "On": GateShape("On", NORMAL, {
        "true": CircuitPin((1, 0), False),
        "false": CircuitPin((-100000, -100000), False)
    }, [(0, 0)]),
    "ByteConstant": GateShape("ByteConstant", NORMAL, {
        "out": CircuitPin((1, 0), False)
    }, [(0, 0)], text=lambda gate: str(gate.custom_data or 0)),

    "ByteSwitch": GateShape("ByteSwitch", NORMAL, {
        "in": CircuitPin((-1, 0), True),
        "control": CircuitPin((0, -1), True),
        "out": CircuitPin((1, 0), False)
    }, [(0, 0)]),

    "Mux": GateShape("Mux", NORMAL, {
        "a": CircuitPin((-1, 0), True),
        "b": CircuitPin((-1, 1), True),
        "control": CircuitPin((-1, -1), True),
        "out": CircuitPin((1, 0), False)
    }, [(0, 0), (0, -1), (0, 1)]),

    "Demux": GateShape("Demux", NORMAL, {
        "control": CircuitPin((-1, 0), True),
        "a": CircuitPin((1, 0), False),
        "b": CircuitPin((1, 1), False),
    }, [(0, 0), (0, 1)]),

    "BiggerDemux": GateShape("BiggerDemux", NORMAL, {
        "a": CircuitPin((-1, -3), True),
        "b": CircuitPin((-1, -2), True),
        "c": CircuitPin((-1, -1), True),

        "deactivate": CircuitPin((0, -4), True),

        "r0": CircuitPin((1, -3), False),
        "r1": CircuitPin((1, -2), False),
        "r2": CircuitPin((1, -1), False),
        "r3": CircuitPin((1, 0), False),
        "r4": CircuitPin((1, 1), False),
        "r5": CircuitPin((1, 2), False),
        "r6": CircuitPin((1, 3), False),
        "r7": CircuitPin((1, 4), False),
    }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),

    "ByteSplitter": GateShape("ByteSplitter", NORMAL, {
        "in": CircuitPin((-1, 0), True),
        "r0": CircuitPin((1, -3), False),
        "r1": CircuitPin((1, -2), False),
        "r2": CircuitPin((1, -1), False),
        "r3": CircuitPin((1, 0), False),
        "r4": CircuitPin((1, 1), False),
        "r5": CircuitPin((1, 2), False),
        "r6": CircuitPin((1, 3), False),
        "r7": CircuitPin((1, 4), False),

    }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
    "ByteMaker": GateShape("ByteMaker", NORMAL, {
        "r0": CircuitPin((-1, -3), True),
        "r1": CircuitPin((-1, -2), True),
        "r2": CircuitPin((-1, -1), True),
        "r3": CircuitPin((-1, 0), True),
        "r4": CircuitPin((-1, 1), True),
        "r5": CircuitPin((-1, 2), True),
        "r6": CircuitPin((-1, 3), True),
        "r7": CircuitPin((-1, 4), True),
        "out": CircuitPin((1, 0), False),

    }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
    "Counter": GateShape("Counter", NORMAL, {
        "in_value": CircuitPin((-1, 0), True, is_delayed=True),
        "overwrite": CircuitPin((-1, -1), True),
        "out_value": CircuitPin((1, 0), False)
    }, [(0, 0), (0, -1)]),
    "Register": GateShape("Register", NORMAL, {
        "load": CircuitPin((-1, -1), True, is_bytes=True),
        "save": CircuitPin((-1, 0), True, is_bytes=True),
        "value": CircuitPin((-1, 1), True, is_bytes=True, is_delayed=True),
        "out": CircuitPin((1, 0), False, is_bytes=True),
    }, [(0, 0), (0, 1), (0, -1)]),
    "ByteNot": GateShape("ByteNot", NORMAL, {
        "in": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, 0), False, is_bytes=True),
    }, [(0, 0)]),
    "ByteAdd": GateShape("ByteAdd", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, -1), False, is_bytes=True),
    }, [(0, 0), (0, -1)]),
    "ByteMul": GateShape("ByteMul", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, 0), False, is_bytes=True),
    }, [(0, 0), (0, -1)]),
    "ByteOr": GateShape("ByteOr", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, 0), False, is_bytes=True),
    }, [(0, 0), (0, -1)]),
    "ByteXor": GateShape("ByteXor", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, 0), False, is_bytes=True),
    }, [(0, 0), (0, -1)]),
    "ByteAdd2": GateShape("ByteAdd2", NORMAL, {
        "carry_in": CircuitPin((-1, -1), True),
        "a": CircuitPin((-1, 0), True, is_bytes=True),
        "b": CircuitPin((-1, 1), True, is_bytes=True),
        "out": CircuitPin((1, -1), False, is_bytes=True),
        "carry_out": CircuitPin((1, 0), False),
    }, [(0, 0), (0, -1), (0, 1)]),

    "ByteLess": GateShape("ByteLess", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "unsigned": CircuitPin((1, -1), False, ),
        "signed": CircuitPin((1, 0), False, ),
    }, [(0, 0), (0, -1)]),

    "ByteEqual": GateShape("ByteEqual", NORMAL, {
        "a": CircuitPin((-1, -1), True, is_bytes=True),
        "b": CircuitPin((-1, 0), True, is_bytes=True),
        "out": CircuitPin((1, -1), False, ),
    }, [(0, 0), (0, -1)]),

    "Ram": GateShape("Ram", NORMAL, {
        "load": CircuitPin((-13, -7), True),
        "save": CircuitPin((-13, -6), True),
        "address": CircuitPin((-13, -5), True),
        "value_in": CircuitPin((-13, -4), True, is_delayed=True),
        "value_out": CircuitPin((13, -7), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16))),

    "Stack": GateShape("Stack", NORMAL, {
        "load": CircuitPin((-13, -7), True),
        "save": CircuitPin((-13, -6), True),
        "value_in": CircuitPin((-13, -5), True, is_delayed=True),
        "value_out": CircuitPin((13, -7), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16))),
    "Program1": GateShape("Program1", NORMAL, {
        "address": CircuitPin((-13, -7), True),
        "out": CircuitPin((13, -7), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
    "Program2": GateShape("Program4", NORMAL, {
        "address": CircuitPin((-13, -7), True),
        "out0": CircuitPin((13, -7), False),
        "out1": CircuitPin((13, -6), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
    "Program3": GateShape("Program4", NORMAL, {
        "address": CircuitPin((-13, -7), True),
        "out0": CircuitPin((13, -7), False),
        "out1": CircuitPin((13, -6), False),
        "out2": CircuitPin((13, -5), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
    "Program4": GateShape("Program4", NORMAL, {
        "address": CircuitPin((-13, -7), True),
        "out0": CircuitPin((13, -7), False),
        "out1": CircuitPin((13, -6), False),
        "out2": CircuitPin((13, -5), False),
        "out3": CircuitPin((13, -4), False),
    }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),

    "Screen": GateShape("Screen", SPECIAL, {
    }, [(0, 0)], big_shape=BigShape((-15, -11), (31, 22))),
    "LevelGate": GateShape("LevelGate", SPECIAL, {}, [(0, 0)])
}

CUSTOM_GATES: dict[str, tuple[Circuit, GateShape]] = {}


def get_path():
    match sys.platform:
        case "Windows" | "win32":
            base_path = Path(os.environ["APPDATA"], r"Godot\app_userdata\Turing Complete")
        case "Darwin":
            base_path = Path("~/Library/Application Support/Godot/app_userdata/Turing Complete").expanduser()
        case "Linux":
            base_path = Path("~/.local/share/godot/app_userdata/Turing Complete").expanduser()
        case _:
            raise ValueError(f"Don't know where to find Turing Complete save on {sys.platform=}")
    if not base_path.exists():
        raise ValueError("You need Turing Complete installed to use this.")
    return base_path


def load_custom(schematics: Path):
    for path in Path(schematics / "component_factory").iterdir():
        circuit = Circuit.parse((path / "circuit.data").read_text())
        CUSTOM_GATES[path.name] = circuit, circuit.compute_gate_shape(path.name)


BASE_PATH = get_path()

SCHEMATICS_PATH = BASE_PATH / "schematics"

load_custom(SCHEMATICS_PATH)


def find_gate(gate: str | GateReference) -> tuple[Circuit | None, GateShape]:
    if isinstance(gate, GateReference):
        if gate.name == "Custom":
            if gate.custom_data in CUSTOM_GATES:
                return CUSTOM_GATES[gate.custom_data]
        gate = gate.name
    return None, DEFAULT_GATES[gate]
