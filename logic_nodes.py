from __future__ import annotations

from abc import abstractmethod
from collections import defaultdict
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
    wires: tuple[Wire, ...]


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
        wires_by_target = defaultdict(list)
        for wire in self.wires:
            wires_by_target[wire.target[0]].append(wire)
            if wire.target[0] is not None:
                s: LogicNodeType
                t: LogicNodeType
                sp: OutputPin
                tp: InputPin

                if wire.source[0] is not None:
                    dep = (Execution(wire.source[0], False, ()),)
                else:
                    dep = ()
                t = self.nodes[wire.target[0]]
                tp = t.inputs[wire.target[1]]
                if tp.delayed:
                    sorter.add(Execution(wire.target[0], True, ()), *dep)
                else:
                    sorter.add(Execution(wire.target[0], False, ()), *dep)

        sorter.prepare()
        order = []
        while sorter.is_active():
            nodes = sorter.get_ready()
            current = []
            for n in nodes:
                sorter.done(n)
                assert isinstance(n, Execution), n
                current.append(Execution(n.node, n.delayed, tuple(wires_by_target[n.node])))
            order.append(tuple(current))
        return tuple(order)

    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray]) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        if state is not None:
            states = {}
            i = 0
            for name, node in sorted(self.nodes.items()):
                if node.state_size:
                    assert i + node.state_size <= len(state)
                    states[name] = state[i:i + node.state_size]
                    i += node.state_size
        values = dict(inputs)
        for step in self.execution_order:
            for exe in step:
                args = {}


NAND1 = DirectLogicNodeType("NAND1",
                            frozendict({"a": InputPin(1, False), "b": InputPin(1, False)}),
                            frozendict({"out": OutputPin(1, False)}), 0,
                            lambda v, _: (frozendict({"r": ~(v["a"] & v["b"])}), None))

NOT1 = CombinedLogicNode(
    "NOT1",
    frozendict({
        "nand": NAND1
    }),
    frozendict({"in": InputPin(1, False)}), frozendict({"out": OutputPin(1, False)}),
    (Wire((None, "in"), ("nand", "a")), Wire((None, "in"), ("nand", "b")),
     Wire(("nand", "out"), (None, "out")),)
)

print(NOT1.execution_order)
