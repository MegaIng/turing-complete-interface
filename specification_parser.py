from __future__ import annotations

from graphlib import TopologicalSorter, CycleError
from pathlib import Path

import lark
from frozendict import frozendict
from lark import Transformer, v_args
from tree_ql import LarkQuery

from logic_nodes import InputPin, OutputPin, NAND_2W1, Wire, CombinedLogicNode, LogicNodeType, SR_LATCH, builtins_gates


class Builder(Transformer):
    def __init__(self, registered):
        self.registered = registered

    @v_args(inline=True)
    def in_pin(self, is_delayed, name, _1, size, _2):
        return name.value, InputPin(int(size or 1), bool(is_delayed))

    @v_args(inline=True)
    def out_pin(self, is_maybe, name, _1, size, _2):
        return name.value, OutputPin(int(size or 1))

    @v_args(inline=True)
    def component(self, name, type_name):
        return name.value, self.registered[type_name.value]

    @v_args(inline=True)
    def name(self, name):
        return name.value

    @v_args(inline=True)
    def sel(self, start, sep=None, end=None):
        start = int(start)
        end = int(end) if end is not None else 0
        if sep is None:
            return (start, start + 1)
        elif sep == ":":
            return (start, end)
        else:
            return (start, end + 1)

    @v_args(inline=True)
    def wire_pin(self, node_name, pin_name, selector):
        node_name = node_name.value if node_name is not None else node_name
        return (node_name, pin_name.value), selector

    @v_args(inline=True)
    def wire(self, source, target):
        return Wire(source[0], target[0], source[1], target[1])

    inputs = frozendict
    outputs = frozendict
    components = frozendict
    wires = tuple

    @v_args(inline=True)
    def start(self, name, ins, outs, nodes, wires):
        return CombinedLogicNode(name, nodes, ins, outs, wires)


parser = lark.Lark(r"""

start: name inputs outputs components wires

name: "name" ":" NAME

_block{elem}: (elem ("," elem)* ","?)? | "{" (elem ((","|";") elem)* (","|";")?)? "}"
inputs: "inputs" ":" _block{in_pin}
outputs: "outputs" ":" _block{out_pin}

!in_pin: ["?"] NAME ["[" INT "]"]
!out_pin: ["?"] NAME ["[" INT "]"]

components: "components" ":" _block{component}

component: NAME ":" NAME

wires: "wires" ":" _block{wire}

wire: wire_pin "->" wire_pin

wire_pin: [NAME "."] NAME ["[" sel "]"]
!sel: INT | INT ":" INT | INT ".." INT

NAME: /\w+/
INT: /\d+/
%ignore /\s+/
""", parser="lalr", maybe_placeholders=True)

name_query = LarkQuery('/name/*[@type=="NAME"]/@value')
deps_query = LarkQuery('/components/component/*[1::2]')


def get_name_of_component(path: Path) -> str:
    tree = parser.parse(path.read_text("utf-8"))
    return name_query.execute(tree, multi=False)


def load_all_components(base_path: Path) -> dict[str, LogicNodeType]:
    parsed = {}
    sorter = TopologicalSorter()
    for spec in base_path.rglob("*.spec"):
        tree = parser.parse(spec.read_text("utf-8"))
        name = name_query.execute(tree, multi=False)
        parsed[name] = tree

        deps = deps_query.execute(tree, multi=True)
        if deps:
            sorter.add(name, *filter(lambda n: n not in builtins_gates, deps))
        else:
            sorter.add(name)
    sorter.prepare()
    compiled = {**builtins_gates}
    builder = Builder(compiled)
    while sorter.is_active():
        for name in sorter.get_ready():
            tree = parsed[name]
            compiled[name] = builder.transform(tree)
            sorter.done(name)
    return compiled
