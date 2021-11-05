import json
from pathlib import Path

from turing_complete_interface.circuit_builder import build_circuit, IOPosition, Space
from turing_complete_interface.circuit_parser import SCHEMATICS_PATH
from turing_complete_interface.level_layouts import get_layout
from turing_complete_interface.verilog_parser import parse_verilog

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", help="Output the .spec file.", action="store_true")
    parser.add_argument("-l", "--level", help="The level to store in. If not set output to stdout", action="store")
    parser.add_argument("-s", "--save", help="The save in the level to store in. Defaults to a new name",
                        action="store")
    parser.add_argument("verilog", help="The verilog file to take as input.", type=Path)

    ns = parser.parse_args()

    node = parse_verilog(ns.verilog.read_text())

    if ns.spec:
        print(node.to_spec())
    space = get_layout(ns.level).new_space()

    circuit = build_circuit(node, IOPosition.from_node(node), space)

    if ns.level is None:
        print(circuit.to_string())
    else:
        level = SCHEMATICS_PATH / ns.level
        if ns.save is None:
            save_folder: Path = level / ns.verilog.stem
            i = 0
            base_stem = save_folder.stem
            while save_folder.exists():
                i += 1
                save_folder = save_folder.with_stem(f"{base_stem}{i}")
        else:
            save_folder = level / ns.save

        save_folder.mkdir(parents=True, exist_ok=True)
        save = save_folder / "circuit.data"
        save.write_text(circuit.to_string())
        print("Wrote to", save)
