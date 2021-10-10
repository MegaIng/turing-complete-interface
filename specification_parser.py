from __future__ import annotations

import lark
from frozendict import frozendict
from lark import Transformer, v_args

from logic_nodes import InputPin, OutputPin, NAND1, Wire, CombinedLogicNode

registered = {
    NAND1.name: NAND1
}


class Builder(Transformer):
    @v_args(inline=True)
    def in_pin(self, is_delayed, name, size):
        return name.value, InputPin(int(size or 1), bool(is_delayed))

    @v_args(inline=True)
    def out_pin(self, is_maybe, name, size):
        return name.value, OutputPin(int(size or 1), bool(is_maybe))

    @v_args(inline=True)
    def component(self, name, type_name):
        return name.value, registered[type_name.value]

    @v_args(inline=True)
    def name(self, name):
        return name.value

    @v_args(inline=True)
    def wire_pin(self, node_name, pin_name, selector):
        print(repr((node_name, pin_name, selector)))
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

NAME: /[^\W\d]\w*/
INT: /\d+/
%ignore /\s+/
""", transformer=Builder(), parser="lalr", maybe_placeholders=True)

node = parser.parse(open("components/basic/not.spec").read())

print(node)
print(hash(node))
