from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from frozendict import frozendict
from lark import Lark, v_args, Token
from lark.visitors import Interpreter, visit_children_decor

from turing_complete_interface.logic_nodes import LogicNodeType, CombinedLogicNode, OutputPin, InputPin, Wire
from turing_complete_interface.specification_parser import spec_components

parser = Lark(r"""
start: disjunction
?disjunction: (disjunction DISJUNCTION)? conjunction
?conjunction: (conjunction [CONJUNCTION])? maybe_pre_negation
?maybe_pre_negation: PRE_NEGATION maybe_pre_negation -> pre_negation 
                   | maybe_post_negation
?maybe_post_negation: maybe_post_negation POST_NEGATION -> post_negation
                    | atom
?atom: /\w+/ -> input
     | "(" disjunction ")"

DISJUNCTION: "∨" | "+" | "∥" | "|" | "||" | "⊕" | "⊻" | "≢" | "⊽"
CONJUNCTION: "∧" | "·" | "&" | "&&" | "⊼"
PRE_NEGATION: "¬" | "˜" | "!" | "~"
POST_NEGATION: "'"
%ignore /\s+/
""", parser="lalr")

OR_OPERATORS = {"∨", "+", "∥", "|", "||"}
NOR_OPERATORS = {"⊽"}
XOR_OPERATORS = {"⊕", "⊻", "≢"}

AND_OPERATORS = {"∧", "·", "&", "&&", None}
NAND_OPERATORS = {"⊼"}
NOT_OPERATORS = {"¬", "˜", "!", "~", "'"}


@dataclass
@v_args(inline=True)
class BuildNode(Interpreter):
    name: str
    nodes: dict[str, LogicNodeType] = field(default_factory=dict)
    inputs: dict[str, InputPin] = field(default_factory=dict)
    outputs: dict[str, OutputPin] = field(default_factory=dict)
    wires: list[Wire] = field(default_factory=list)

    def start(self, base):
        self.visit(base)
        return CombinedLogicNode(self.name, frozendict(self.nodes), frozendict(self.inputs), frozendict(self.outputs),
                                 tuple(self.wires))

    def _add_node(self, component: LogicNodeType, *args):
        self.nodes[i := str(len(self.nodes) + 1)] = component
        for pin, target in zip(component.inputs, args, strict=True):
            self.wires.append(Wire((i, pin), target))
        return i, next(iter(component.outputs))

    def disjunction(self, a, op, b):
        a = self.visit(a)
        b = self.visit(b)
        if op.value in OR_OPERATORS:
            self._add_node(spec_components["OR_2W1"], a, b)
        elif op.value in NOR_OPERATORS:
            return self._add_node(spec_components["NOR_2W1"], a, b)
        else:
            raise ValueError(op)

    def conjunction(self, a, op, b):
        a = self.visit(a)
        b = self.visit(b)
        if op is None or op.value in AND_OPERATORS:
            self._add_node(spec_components["AND_2W1"], a, b)
        elif op.value in NAND_OPERATORS:
            return self._add_node(spec_components["NAND_2W1"], a, b)
        else:
            raise ValueError(op)

    def input(self, name: Token):
        if name in self.inputs:
            self.inputs[name.value] = InputPin(1)
        return (None, name.value)

    def pre_negation(self, op, base):
        base = self.visit(base)
        if op in NOT_OPERATORS:
            return self._add_node(spec_components["NOT_1W1"], base)
        else:
            raise ValueError(op)

    def post_negation(self, base, op):
        base = self.visit(base)
        if op in NOT_OPERATORS:
            return self._add_node(spec_components["NOT_1W1"], base)
        else:
            raise ValueError(op)

    def __default__(self, *args):
        raise NotImplementedError(args)


def from_logic_expression(name: str, text: str) -> CombinedLogicNode:
    tree = parser.parse(text)
    return BuildNode(name).visit(tree)

