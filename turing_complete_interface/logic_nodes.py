from __future__ import annotations

from abc import abstractmethod, ABC
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property, reduce, cache
from operator import or_
from typing import Optional, Callable, Protocol, Literal, Any, Mapping

from bitarray import bitarray, frozenbitarray, bits2bytes
from bitarray.util import int2ba, ba2int
from frozendict import frozendict
from graphlib import TopologicalSorter


@dataclass(frozen=True)
class InputPin:
    bits: int
    delayed: bool = None


@dataclass(frozen=True)
class OutputPin:
    bits: int


class LogicNodeType(ABC):
    name: str
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    state_size: int

    @abstractmethod
    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray],
                 delayed: bool | Literal["toplevel"]) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        raise NotImplementedError

    @cached_property
    def any_delayed(self) -> bool:
        return any(i.delayed for i in self.inputs.values())

    def calculate(self, state: int = None, /, **values: int) -> tuple[int | None, dict[str, int], Any]:
        inputs = {name: int2ba(value, self.inputs[name].bits, endian="little") for name, value in values.items()}
        if state is None:
            actual_state = None
        elif isinstance(state, int):
            actual_state = int2ba(state, self.state_size, endian="little")
        else:
            actual_state = state
        res, s, extra = self.evaluate(frozendict(inputs), actual_state, True)
        res = {name: ba2int(v) for name, v in res.items()}
        if s is None:
            return None, res, extra
        else:
            return ba2int(s), res, extra

    def create_state(self) -> frozenbitarray | None:
        if not self.state_size:
            return None
        else:
            b = bitarray(self.state_size)
            b[:] = 0
            return frozenbitarray(b)


@dataclass(frozen=True)
class DirectLogicNodeType(LogicNodeType):
    name: str
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    state_size: int
    func: Callable[[frozendict[str, frozenbitarray], Optional[frozenbitarray], bool],
                   tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]]

    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray], delayed: bool) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
        return (self.func(inputs, state, delayed) + (None,))[:3]


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


def file_safe_name(s):
    return s.replace(".", "_")


@dataclass(frozen=True)
class CombinedLogicNode(LogicNodeType):
    name: str
    nodes: frozendict[str, LogicNodeType]
    inputs: frozendict[str, InputPin]
    outputs: frozendict[str, OutputPin]
    wires: tuple[Wire, ...]

    def renamed(self, mapping: Mapping[str, str]) -> CombinedLogicNode:
        r = lambda n: mapping.get(n, n)
        return CombinedLogicNode(self.name, frozendict({
            r(name): node for name, node in self.nodes.items()
        }), frozendict({
            r(name): inp for name, inp in self.inputs.items()
        }), frozendict({
            r(name): out for name, out in self.outputs.items()
        }), tuple(
            Wire((r(wire.source[0]),
                  wire.source[1] if wire.source[0] is not None else r(wire.source[1])),
                 (r(wire.target[0]),
                  wire.target[1] if wire.target[0] is not None else r(wire.target[1])),
                 wire.source_bits, wire.target_bits)
            for wire in self.wires
        ))

    @cached_property
    def state_size(self):
        return sum(node.state_size for node in self.nodes.values())

    @cached_property
    def wires_by_target(self) -> frozendict[str | None, tuple[Wire, ...]]:
        wires_by_target = defaultdict(list)
        for wire in self.wires:
            wires_by_target[wire.target[0]].append(wire)
        return frozendict({n: tuple(ws) for n, ws in wires_by_target.items()})

    def to_spec(self, rename: Callable[[str], str] = lambda s: s) -> str:
        def group(elements):
            if sum(len(e) for e in elements) > 40:
                elements = ",\n    ".join(elements)
                return f"{{\n    {elements}\n}}"
            else:
                return ", ".join(elements)

        inputs = [
            f"{'?' if i.delayed else ''}{rename(name)}{f'[{i.bits}]' if i.bits != 1 else ''}"
            for name, i in self.inputs.items()
        ]
        outputs = [
            f"{rename(name)}{f'[{i.bits}]' if i.bits != 1 else ''}"
            for name, i in self.outputs.items()
        ]
        components = [
            f"{rename(name)}: {node.name}" for name, node in self.nodes.items()
        ]
        f = lambda t: (rename(t[1]) if t[0] is None else f'{rename(t[0])}.{rename(t[1])}')
        g = lambda t: '' if t is None else f'[{t[0]}:{t[1]}]'
        wires = [
            f"{f(wire.source)}{g(wire.source_bits)} -> {f(wire.target)}{g(wire.target_bits)}"
            for wire in self.wires
        ]
        return f"""\
name: {self.name}

inputs: {group(inputs)}
outputs: {group(outputs)}

components: {group(components)}

wires: {group(wires)}
"""

    @cached_property
    def execution_order(self) -> tuple[tuple[Execution, ...], ...]:
        try:
            sorter = TopologicalSorter({})
            for wire in self.wires:
                if wire.target[0] is not None:
                    s: LogicNodeType
                    t: LogicNodeType
                    sp: OutputPin
                    tp: InputPin

                    if wire.source[0] is not None:
                        dep = (Execution(wire.source[0], False),)
                    else:
                        dep = ()
                    t = self.nodes[wire.target[0]]
                    try:
                        tp = t.inputs[wire.target[1]]
                    except KeyError:
                        raise KeyError(wire)
                    if tp.delayed:
                        sorter.add(Execution(wire.target[0], True), *dep)
                    else:
                        sorter.add(Execution(wire.target[0], False), *dep)
                        if t.any_delayed:
                            sorter.add(Execution(wire.target[0], True), *dep)
                elif wire.source[0] is not None:
                    sorter.add(Execution(wire.source[0], False))

            sorter.prepare()
            order = []
            while sorter.is_active():
                nodes = sorter.get_ready()
                current = []
                for n in nodes:
                    sorter.done(n)
                    assert isinstance(n, Execution), n
                    current.append(Execution(n.node, n.delayed))
                order.append(tuple(current))
            return tuple(order)
        except Exception as e:
            raise type(e)(self.name, *e.args)

    def evaluate(self, inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray],
                 delayed: bool) -> \
            tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray], Any]:
        try:
            states = {}
            if state is not None:
                i = 0
                for name, node in sorted(self.nodes.items()):
                    if node.state_size:
                        assert i + node.state_size <= len(state)
                        states[name] = state[i:i + node.state_size]
                        i += node.state_size

            values = {}
            for name, value in inputs.items():
                pin = self.inputs[name]
                assert len(value) == pin.bits, (name, pin, value)
                values[None, name] = value
            for step in self.execution_order:
                for exe in step:
                    node = self.nodes[exe.node]
                    args = {name: bitarray(inp.bits, endian="little") for name, inp in node.inputs.items()}
                    for wire in self.wires_by_target.get(exe.node, ()):
                        if node.inputs[wire.target[1]].delayed and not exe.delayed:
                            continue
                        source = values.get(wire.source, None)
                        if source is None:
                            source = frozenbitarray(node.inputs[wire.target[1]].bits, endian="little")
                        target = args[wire.target[1]]
                        if wire.source_bits is not None:
                            source = source[wire.source_bits[0]:wire.source_bits[1]]
                        if wire.target_bits is not None:
                            target[wire.target_bits[0]:wire.target_bits[1]] = source
                        else:
                            target[:] = source
                    args = {name: frozenbitarray(v) for name, v in args.items()}
                    try:
                        res, new_state, _ = node.evaluate(frozendict(args), states.get(exe.node, None),
                                                          exe.delayed and delayed)
                    except Exception as e:
                        raise type(e)(exe, *e.args)
                    if new_state is not None and states is not None and exe.delayed and delayed:
                        states[exe.node] = new_state
                    values.update({(exe.node, name): value for name, value in res.items()})

            out = {name: bitarray(out.bits, endian="little") for name, out in self.outputs.items()}
            for wire in self.wires_by_target[None]:
                source = values[wire.source]
                try:
                    target = out[wire.target[1]]
                except KeyError:
                    raise KeyError(wire, out)
                if wire.source_bits is not None:
                    source = source[wire.source_bits[0]:wire.source_bits[1]]
                if wire.target_bits is not None:
                    target[wire.target_bits[0]:wire.target_bits[1]] = source
                else:
                    target[:] = source
            out = frozendict({name: frozenbitarray(v) for name, v in out.items()})
            if state is not None:
                new_state = bitarray(self.state_size, endian="little")
                i = 0
                for name, node in sorted(self.nodes.items()):
                    if node.state_size:
                        assert i + node.state_size <= len(state)
                        new_state[i:i + node.state_size] = states[name]
                        i += node.state_size
                new_state = frozenbitarray(new_state)
            else:
                new_state = None
            return out, new_state, values
        except Exception as e:
            raise type(e)(self.name, *e.args)


def _nand(args, _1, _2):
    try:
        return frozendict({"out": ~(args["a"] & args["b"])}), None
    except Exception as e:
        raise type(e)(args, *e.args)


NAND_2W1 = DirectLogicNodeType(
    "NAND_2W1",
    frozendict({"a": InputPin(1, False), "b": InputPin(1, False)}),
    frozendict({"out": OutputPin(1)}), 0, _nand
)


def _sr_latch(inputs: frozendict[str, frozenbitarray], state: Optional[frozenbitarray],
              delayed: bool) -> tuple[frozendict[str, Optional[frozenbitarray]], Optional[frozenbitarray]]:
    assert state is not None, state
    if delayed:
        new_state = bitarray(state, endian="little")
        if inputs["write_pos"][0]:
            new_state[0] = True
        if inputs["write_neg"][0]:
            new_state[0] = False
        new_state = frozenbitarray(new_state)
        return frozendict({
            "pos": new_state, "neg": ~new_state
        }), new_state
    else:
        return frozendict({
            "pos": state, "neg": ~state
        }), None


SR_LATCH = DirectLogicNodeType(
    "SR_LATCH",
    frozendict({"write_pos": InputPin(1, True), "write_neg": InputPin(1, True)}),
    frozendict({"neg": OutputPin(1), "pos": OutputPin(1)}), 1,
    _sr_latch
)

_false = frozenbitarray("0")
_true = frozenbitarray("1")


CONST = DirectLogicNodeType(
    "CONST",
    frozendict(), frozendict({
        "true": OutputPin(1), "false": OutputPin(1)
    }), 0,
    lambda _, _1, _2: (frozendict({"true": _true, "false": _false}), None)
)

builtins_gates = {
    NAND_2W1.name: NAND_2W1,
    SR_LATCH.name: SR_LATCH,
    CONST.name: CONST
}


@cache
def build_or(*names: str, bit_size: int = 1, gate_name="OR_{wire_count}W{bit_size}",
             out_name: str = "out") -> LogicNodeType:
    def _or_func(args, _, _1):
        return frozendict({out_name: reduce(or_, args.values())}), None

    gate_name = gate_name.format(wire_count=len(names), bit_size=bit_size)
    return DirectLogicNodeType(
        gate_name, frozendict(dict.fromkeys(names, InputPin(bit_size, False))),
        frozendict({out_name: OutputPin(bit_size)}), 0, _or_func
    )


for n in range(2, 32 + 1):
    g = build_or(*map(str, range(n)))
    builtins_gates[g.name] = g
