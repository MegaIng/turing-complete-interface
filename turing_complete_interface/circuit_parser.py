from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


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


# DEFAULT_GATES: dict[str, GateShape] = {
#     "Input1": GateShape("Input1", SPECIAL, {
#         "value": CircuitPin((1, 0), False)
#     }, [(0, 0), (0, -1), (0, 1)], True),
#     "Input2": GateShape("Input2", SPECIAL, {
#         "a": CircuitPin((0, 1), False),
#         "b": CircuitPin((0, -1), False)
#     }, [(-1, 1), (-1, 0), (-1, -1), (0, 0)], True),
#     "Input3": GateShape("Input4", SPECIAL, {
#         "a": CircuitPin((1, -2), False),
#         "b": CircuitPin((1, -1), False),
#         "c": CircuitPin((1, 0), False),
#     }, [(0, -2), (0, -1), (0, 0)], True),
#     "Input4": GateShape("Input4", SPECIAL, {
#         "a": CircuitPin((1, -2), False),
#         "b": CircuitPin((1, -1), False),
#         "c": CircuitPin((1, 0), False),
#         "d": CircuitPin((1, 1), False)
#     }, [(0, -2), (0, -1), (0, 0), (0, 1)], True),
#     "Input1B": GateShape("Input1B", SPECIAL, {
#         "value": CircuitPin((1, 0), False, True)
#     }, [(0, 0), (0, -1)], True),
#     "Input1BConditions": GateShape("Input1BConditions", SPECIAL, {
#         "value": CircuitPin((1, 0), False, True)
#     }, [(0, 0), (0, -1)], True),
#     "Input1_1B": GateShape("Output1_1B", SPECIAL, {
#         "value": CircuitPin((1, 0), False, is_bytes=True),
#         "control": CircuitPin((0, 1), True)
#     }, [(0, 0), (0, -1)], True),
#
#     "Output1": GateShape("Output1", SPECIAL, {
#         "value": CircuitPin((-1, 0), True)
#     }, [(0, 0), (0, 1), (0, -1)], True),
#     "Output1B": GateShape("Output1B", SPECIAL, {
#         "value": CircuitPin((-1, 0), True, is_bytes=True)
#     }, [(0, 0), (0, 1), (0, -1)], True),
#     "Output1_1B": GateShape("Output1_1B", SPECIAL, {
#         "value": CircuitPin((-1, 0), True, is_bytes=True),
#         "control": CircuitPin((0, 1), True)
#     }, [(0, 0), (0, -1)], True),
#     "Output1Car": GateShape("Output1Car", SPECIAL, {
#         "value": CircuitPin((-1, 0), True)
#     }, [(0, 0), (0, 1), (0, -1)], True),
#     "Output1Sum": GateShape("Output1Sum", SPECIAL, {
#         "value": CircuitPin((-1, 0), True)
#     }, [(0, 0), (0, 1), (0, -1)], True),
#     "OutputCounter": GateShape("OutputCounter", SPECIAL, {
#         "a": CircuitPin((-1, -1), True),
#         "b": CircuitPin((-1, 0), True),
#         "c": CircuitPin((-1, 1), True)
#     }, [(0, 0), (0, 1), (0, -1)], True),
#     "Output4": GateShape("Output4", SPECIAL, {
#         "a": CircuitPin((-1, -2), True),
#         "b": CircuitPin((-1, -1), True),
#         "c": CircuitPin((-1, 0), True),
#         "d": CircuitPin((-1, 1), True)
#     }, [(0, 0), (0, 1), (0, 2), (0, -1)], True),
#
#     "Nand": GateShape("Nand", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "And": GateShape("And", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Or": GateShape("Or", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Nor": GateShape("Nor", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Xor": GateShape("Xor", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Xnor": GateShape("Xnor", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Or3": GateShape("Or3", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, 0), True),
#         "c": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "And3": GateShape("And3", NORMAL, {
#         "a": CircuitPin((-1, 1), True),
#         "b": CircuitPin((-1, 0), True),
#         "c": CircuitPin((-1, -1), True),
#         "out": CircuitPin((2, 0), False)
#     }, [(0, 0), (0, 1), (0, -1), (1, 0)]),
#     "Not": GateShape("Not", NORMAL, {
#         "in": CircuitPin((-1, 0), True),
#         "out": CircuitPin((1, 0), False)
#     }, [(0, 0)]),
#     "Buffer": GateShape("Buffer", NORMAL, {
#         "in": CircuitPin((-1, 0), True),
#         "out": CircuitPin((1, 0), False)
#     }, [(0, 0)]),
#     "On": GateShape("On", NORMAL, {
#         "true": CircuitPin((1, 0), False),
#         "false": CircuitPin((-100000, -100000), False)
#     }, [(0, 0)]),
#     "ByteConstant": GateShape("ByteConstant", NORMAL, {
#         "out": CircuitPin((1, 0), False, is_bytes=True)
#     }, [(0, 0)], text=lambda gate: str(gate.custom_data or 0)),
#
#     "ByteSwitch": GateShape("ByteSwitch", NORMAL, {
#         "in": CircuitPin((-1, 0), True, is_bytes=True),
#         "control": CircuitPin((0, -1), True),
#         "out": CircuitPin((1, 0), False, is_bytes=True)
#     }, [(0, 0)]),
#
#     "Mux": GateShape("Mux", NORMAL, {
#         "a": CircuitPin((-1, 0), True, is_bytes=True),
#         "b": CircuitPin((-1, 1), True, is_bytes=True),
#         "control": CircuitPin((-1, -1), True),
#         "out": CircuitPin((1, 0), False, is_bytes=True)
#     }, [(0, 0), (0, -1), (0, 1)]),
#
#     "Demux": GateShape("Demux", NORMAL, {
#         "control": CircuitPin((-1, 0), True),
#         "a": CircuitPin((1, 0), False),
#         "b": CircuitPin((1, 1), False),
#     }, [(0, 0), (0, 1)]),
#
#     "BiggerDemux": GateShape("BiggerDemux", NORMAL, {
#         "a": CircuitPin((-1, -3), True),
#         "b": CircuitPin((-1, -2), True),
#         "c": CircuitPin((-1, -1), True),
#
#         "deactivate": CircuitPin((0, -4), True),
#
#         "r0": CircuitPin((1, -3), False),
#         "r1": CircuitPin((1, -2), False),
#         "r2": CircuitPin((1, -1), False),
#         "r3": CircuitPin((1, 0), False),
#         "r4": CircuitPin((1, 1), False),
#         "r5": CircuitPin((1, 2), False),
#         "r6": CircuitPin((1, 3), False),
#         "r7": CircuitPin((1, 4), False),
#     }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
#
#     "ByteSplitter": GateShape("ByteSplitter", NORMAL, {
#         "in": CircuitPin((-1, 0), True, is_bytes=True),
#         "r0": CircuitPin((1, -3), False),
#         "r1": CircuitPin((1, -2), False),
#         "r2": CircuitPin((1, -1), False),
#         "r3": CircuitPin((1, 0), False),
#         "r4": CircuitPin((1, 1), False),
#         "r5": CircuitPin((1, 2), False),
#         "r6": CircuitPin((1, 3), False),
#         "r7": CircuitPin((1, 4), False),
#
#     }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
#     "ByteMaker": GateShape("ByteMaker", NORMAL, {
#         "r0": CircuitPin((-1, -3), True),
#         "r1": CircuitPin((-1, -2), True),
#         "r2": CircuitPin((-1, -1), True),
#         "r3": CircuitPin((-1, 0), True),
#         "r4": CircuitPin((-1, 1), True),
#         "r5": CircuitPin((-1, 2), True),
#         "r6": CircuitPin((-1, 3), True),
#         "r7": CircuitPin((-1, 4), True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#
#     }, [(0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
#     "Counter": GateShape("Counter", NORMAL, {
#         "in": CircuitPin((-1, 0), True, is_bytes=True, is_delayed=True),
#         "overwrite": CircuitPin((-1, -1), True),
#         "out": CircuitPin((1, 0), False, is_bytes=True)
#     }, [(0, 0), (0, -1)]),
#     "Register": GateShape("Register", NORMAL, {
#         "load": CircuitPin((-1, -1), True),
#         "save": CircuitPin((-1, 0), True, is_delayed=True),
#         "value": CircuitPin((-1, 1), True, is_bytes=True, is_delayed=True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#     }, [(0, 0), (0, 1), (0, -1)]),
#     "ByteNot": GateShape("ByteNot", NORMAL, {
#         "in": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#     }, [(0, 0)]),
#     "ByteAdd": GateShape("ByteAdd", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, -1), False, is_bytes=True),
#     }, [(0, 0), (0, -1)]),
#     "ByteMul": GateShape("ByteMul", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#     }, [(0, 0), (0, -1)]),
#     "ByteOr": GateShape("ByteOr", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#     }, [(0, 0), (0, -1)]),
#     "ByteXor": GateShape("ByteXor", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, 0), False, is_bytes=True),
#     }, [(0, 0), (0, -1)]),
#     "ByteAdd2": GateShape("ByteAdd2", NORMAL, {
#         "carry_in": CircuitPin((-1, -1), True),
#         "a": CircuitPin((-1, 0), True, is_bytes=True),
#         "b": CircuitPin((-1, 1), True, is_bytes=True),
#         "out": CircuitPin((1, -1), False, is_bytes=True),
#         "carry_out": CircuitPin((1, 0), False),
#     }, [(0, 0), (0, -1), (0, 1)]),
#
#     "ByteLess": GateShape("ByteLess", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "unsigned": CircuitPin((1, -1), False, ),
#         "signed": CircuitPin((1, 0), False, ),
#     }, [(0, 0), (0, -1)]),
#
#     "ByteEqual": GateShape("ByteEqual", NORMAL, {
#         "a": CircuitPin((-1, -1), True, is_bytes=True),
#         "b": CircuitPin((-1, 0), True, is_bytes=True),
#         "out": CircuitPin((1, -1), False, ),
#     }, [(0, 0), (0, -1)]),
#
#     "Ram": GateShape("Ram", NORMAL, {
#         "load": CircuitPin((-13, -7), True),
#         "save": CircuitPin((-13, -6), True),
#         "address": CircuitPin((-13, -5), True, is_bytes=True),
#         "value_in": CircuitPin((-13, -4), True, is_bytes=True, is_delayed=True),
#         "value_out": CircuitPin((13, -7), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16))),
#
#     "Stack": GateShape("Stack", NORMAL, {
#         "load": CircuitPin((-13, -7), True),
#         "save": CircuitPin((-13, -6), True),
#         "value_in": CircuitPin((-13, -5), True, is_bytes=True, is_delayed=True),
#         "value_out": CircuitPin((13, -7), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16))),
#     "Program1": GateShape("Program1", NORMAL, {
#         "address": CircuitPin((-13, -7), True, is_bytes=True),
#         "out": CircuitPin((13, -7), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
#     "Program2": GateShape("Program4", NORMAL, {
#         "address": CircuitPin((-13, -7), True, is_bytes=True),
#         "out0": CircuitPin((13, -7), False, is_bytes=True),
#         "out1": CircuitPin((13, -6), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
#     "Program3": GateShape("Program4", NORMAL, {
#         "address": CircuitPin((-13, -7), True, is_bytes=True),
#         "out0": CircuitPin((13, -7), False, is_bytes=True),
#         "out1": CircuitPin((13, -6), False, is_bytes=True),
#         "out2": CircuitPin((13, -5), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
#     "Program4": GateShape("Program4", NORMAL, {
#         "address": CircuitPin((-13, -7), True, is_bytes=True),
#         "out0": CircuitPin((13, -7), False, is_bytes=True),
#         "out1": CircuitPin((13, -6), False, is_bytes=True),
#         "out2": CircuitPin((13, -5), False, is_bytes=True),
#         "out3": CircuitPin((13, -4), False, is_bytes=True),
#     }, [], big_shape=BigShape((-12, -7), (25, 16)), text=lambda gate: gate.name),
#
#     "AsciiScreen": GateShape("AsciiScreen", NORMAL, {
#         "write_cursor": CircuitPin((-10, -6), True),
#         "cursor": CircuitPin((-10, -5), True, is_bytes=True),
#         "write_color": CircuitPin((-10, -4), True),
#         "color": CircuitPin((-10, -3), True, is_bytes=True),
#         "write_char": CircuitPin((-10, -2), True),
#         "char": CircuitPin((-10, -1), True, is_bytes=True),
#     }, [(0, 0)], big_shape=BigShape((-9, -6), (19, 13))),
#
#     "Keyboard": GateShape("Keyboard", NORMAL, {
#         "enable": CircuitPin((-2, -1), True),
#         "out": CircuitPin((2, -1), False, is_bytes=True)
#     }, [(0, 0)], big_shape=BigShape((-1, -2), (3, 5))),
#
#     "Screen": GateShape("Screen", SPECIAL, {
#     }, [(0, 0)], big_shape=BigShape((-15, -11), (31, 22))),
#     "LevelGate": GateShape("LevelGate", SPECIAL, {}, [(0, 0)])
# }


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


BASE_PATH = get_path()

SCHEMATICS_PATH = BASE_PATH / "schematics"
