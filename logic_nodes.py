from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Optional, Callable, Protocol

from bitarray import bitarray, frozenbitarray
from frozendict import frozendict
from graphlib import TopologicalSorter


@dataclass(frozen=True)
class InputPin:
    bits: int
    delayed: bool


@dataclass(frozen=True)
class OutputPin:
    bits: int
    can_be_missing: bool


class LogicNodeType(Protocol):
    name: str
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    state_size: int

    @abstractmethod
    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray]) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        raise NotImplementedError


@dataclass(frozen=True)
class DirectLogicNodeType:
    name: str
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    state_size: int
    func: Callable[[frozendict[str, frozenbitarray], Optional[frozenbitarray]],
                   tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]]

    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray]) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        return self.func(inputs, state)


@dataclass(frozen=True)
class Wire:
    source: tuple[str | None, str]
    target: tuple[str | None, str]
    source_bits: tuple[int, int] | None = None  # None means all
    target_bits: tuple[int, int] | None = None


@dataclass(frozen=True)
class Execution:
    node: str
    delayed: bool


@dataclass(frozen=True)
class CombinedLogicNode:
    name: str
    nodes: frozendict[str, LogicNodeType]
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    wires: tuple[Wire, ...]

    @cached_property
    def execution_order(self) -> tuple[tuple[Execution, ...], ...]:
        sorter = TopologicalSorter({})
        for wire in self.wires:
            sorter.add(wire.tar)

        order = []

        return tuple(order)

    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray]) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        pass


NAND1 = DirectLogicNodeType("NAND1",
                            frozendict({"a": InputPin(1, False), "b": InputPin(1, False)}),
                            frozendict({"r": OutputPin(1, False)}), 0,
                            lambda v, _: (frozendict({"r": ~(v["a"] & v["b"])}), None))
