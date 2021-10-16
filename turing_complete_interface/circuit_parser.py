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
    is_byte: bool = False
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
