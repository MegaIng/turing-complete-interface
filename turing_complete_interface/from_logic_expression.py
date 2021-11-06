from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, log
from typing import Dict, Any
from itertools import zip_longest

from frozendict import frozendict
from lark import Lark, v_args, Token, Visitor
from lark.visitors import Interpreter, visit_children_decor

from turing_complete_interface.logic_nodes import LogicNodeType, CombinedLogicNode, OutputPin, InputPin, Wire, NodePin
from turing_complete_interface.specification_parser import spec_components

parser = Lark(r"""
start: assignment+ | lone_expression
lone_expression: disjunction
assignment: "!" NAME "=" disjunction -> out_assignment
          | NAME "=" disjunction
?disjunction: (conjunction DISJUNCTION)* conjunction
?conjunction: (maybe_pre_negation CONJUNCTION)* maybe_pre_negation
?maybe_pre_negation: PRE_NEGATION maybe_pre_negation -> pre_negation 
                   | maybe_post_negation
?maybe_post_negation: maybe_post_negation POST_NEGATION -> post_negation
                    | atom
?atom: NAME -> ref
     | "(" disjunction ")"

DISJUNCTION: "∨" | "+" | "∥" | "|" | "||" | "⊕" | "⊻" | "≢" | "⊽"
CONJUNCTION: "∧" | "·" | "&" | "&&" | "⊼"
PRE_NEGATION: "¬" | "˜" | "!" | "~"
POST_NEGATION: "'"
NAME: /\w+/
%ignore /\s+/
""", parser="lalr")

OR_OPERATORS = frozenset({"∨", "+", "∥", "|", "||"})
NOR_OPERATORS = frozenset({"⊽"})
XOR_OPERATORS = frozenset({"⊕", "⊻", "≢"})

AND_OPERATORS = frozenset({"∧", "·", "&", "&&", None})
NAND_OPERATORS = frozenset({"⊼"})
NOT_OPERATORS = frozenset({"¬", "˜", "!", "~", "'"})

INFIX_OPERATORS = {
    n: op for ns, op in {
        OR_OPERATORS: "or",
        NOR_OPERATORS: "nor",
        XOR_OPERATORS: "xor",
        AND_OPERATORS: "and",
        NAND_OPERATORS: "nand",
    }.items() for n in ns
}


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


@dataclass
class _CollectNames(Visitor):
    used_names: set[str] = field(default_factory=set)
    assigned_names: set[str] = field(default_factory=set)
    explicit_export_names: set[str] = field(default_factory=set)

    def ref(self, tree):
        self.used_names.add(tree.children[0].value)

    def out_assignment(self, tree):
        name = tree.children[0].value
        self.assigned_names.add(name)
        self.explicit_export_names.add(name)

    def assignment(self, tree):
        name = tree.children[0].value
        self.assigned_names.add(name)


@dataclass
class BuildNode(Interpreter):
    name: str
    nodes: dict[str, LogicNodeType] = field(default_factory=dict)
    inputs: dict[str, InputPin] = field(default_factory=dict)
    outputs: dict[str, OutputPin] = field(default_factory=dict)
    not_cache: dict[NodePin, NodePin] = field(default_factory=dict)
    wires: list[Wire] = field(default_factory=list)

    # Contain wires which require missing information, e.g. the start of a temporary wire for example.
    # half_wires: list[]

    def start(self, tree):
        cn = _CollectNames()
        cn.visit(tree)
        assert len(cn.used_names & cn.assigned_names) == 0, "Can't deal with temporary variables right now"
        self.inputs = {name: InputPin(1) for name in cn.used_names - cn.assigned_names}
        self.outputs = {name: OutputPin(1) for name in ((cn.assigned_names - cn.used_names) | cn.explicit_export_names)}
        self.visit_children(tree)
        return CombinedLogicNode(self.name, frozendict(self.nodes), frozendict(self.inputs), frozendict(self.outputs),
                                 tuple(self.wires))

    def _add_node(self, component: LogicNodeType, *args):
        self.nodes[i := str(len(self.nodes) + 1)] = component
        for pin, target in zip(component.inputs, args, strict=True):
            self.wires.append(Wire(target, (i, pin), (0, 1), (0, 1)))
        return i, next(iter(component.outputs))

    def _buffer(self, source):
        return self._add_node(spec_components["BUFFER_1W1"], source)

    def _build_tree_3(self, values, nodes):
        two = spec_components[nodes[0]]
        three = spec_components[nodes[1]]
        next_layer = []
        while len(values) > 1:
            for group in grouper(values, 3):
                if group[2] is not None:
                    next_layer.append(self._add_node(three, *group[:3]))
                elif group[1] is not None:
                    next_layer.append(self._add_node(two, *group[:2]))
                else:
                    next_layer.append(group[0])
            values = next_layer
            next_layer = []
        return values[0]

    def _infix(self, tree):
        operators = {INFIX_OPERATORS[op] for op in tree.children[1::2]}
        assert len(operators) == 1, f"Can't have more than one operator in a chain {operators}"
        op, = operators
        values = [self.visit(v) for v in tree.children[::2]]
        if op in {"or", "and"}:
            return self._build_tree_3(values, {"or": ["OR_2W1", "OR_3W1"], "and": ["AND_2W1", "AND_3W1"]}[op])
        else:
            raise NotImplementedError(op)

    conjunction = disjunction = _infix

    @v_args(inline=True)
    def assignment(self, name: Token, expression):
        expression = self.visit(expression)
        assert name.value in self.outputs
        self.wires.append(Wire(expression, (None, name.value), (0,1),(0,1)))

    @v_args(inline=True)
    def ref(self, name: Token):
        assert name in self.inputs
        return (None, name.value)

    def _not(self, base):
        if base not in self.not_cache:
            self.not_cache[base] = self._add_node(spec_components["NOT_1W1"], base)
            self.not_cache[self.not_cache[base]] = base  # A'' = A
        return self.not_cache[base]

    @v_args(inline=True)
    def pre_negation(self, op, base):
        base = self.visit(base)
        if op in NOT_OPERATORS:
            return self._not(base)
        else:
            raise ValueError(op)

    @v_args(inline=True)
    def post_negation(self, base, op):
        base = self.visit(base)
        if op in NOT_OPERATORS:
            return self._not(base)
        else:
            raise ValueError(op)

    def __default__(self, *args):
        raise NotImplementedError(args)


def from_logic_expression(name: str, text: str) -> CombinedLogicNode:
    tree = parser.parse(text)
    return BuildNode(name).visit(tree)
