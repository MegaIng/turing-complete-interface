from pathlib import Path
from lark import Lark

assembler_parser = Lark(r"""
start: line ("\n"+ line)* "\n"*
line: "const" NAME value  -> const_def
    | "label" NAME        -> label_def
    | value+
!value: _atom (OP _atom)*
OP: "+" | "-" | "|" | "&" | "^" | "*" | "/"
_atom: NAME | NUMBER
NUMBER: /\d+/
NAME: /[^\d+\-|&^*\/#\s][^+\-|&^*\/#\s]*/
%ignore /#[^\n]/
%ignore / /
""", parser="lalr")


def assemble(save_path: Path, assembly_file: Path) -> bytes:
    def calc(*args: str) -> int:
        if len(args) == 1:
            return int(args[0]) if isinstance(args[0], int) or args[0].isdigit() else mapping.get(args[0], 0)
        else:
            assert (len(args) - 1) % 2 == 0, args
            return calc(eval(f"{calc(args[0])} {args[1]} {calc(args[2])}"), *args[3:])

    out = bytearray(256)
    mapping = {
        line.strip().split()[0]: int(line.strip().split()[1])
        for line in (save_path / "assembly.data").read_text().splitlines()
    }
    raw = assembly_file.read_text()
    tree = assembler_parser.parse(raw)
    i = 0
    for line in tree.children:
        if line.data == "label_def":
            mapping[line.children[0].value] = i
        elif line.data == "line":
            assert (len(line.children)in(2,)), line
            i += len(line.children)
        else:
            assert line.data == "const_def", line
    for line in tree.children:
        if line.data == "const_def":
            mapping[line.children[0].value] = calc(*line.children[1].children)
    i = 0
    for line in tree.children:
        if line.data == "line":
            for v in line.children:
                out[i] = calc(*v.children)
                i += 1
    return bytes(out)
