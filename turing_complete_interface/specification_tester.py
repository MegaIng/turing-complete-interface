import argparse
import sys
from ast import literal_eval
from pathlib import Path
import tkinter as tk
from pprint import pprint

from lark import LarkError

from .logic_nodes import LogicNodeType
from .specification_parser import load_all_components, get_name_of_component


class BitsInput(tk.Frame):
    def __init__(self, master, name: str, bit_size: int, locked=False, delayed: bool = False):
        super(BitsInput, self).__init__(master)
        self.bit_size = bit_size
        self.label = tk.Label(self, text=("?"[:delayed]) + (f"{name}[{bit_size}]" if bit_size != 1 else name))
        self.label.pack()
        self._value = 0
        self.bit_frame = None
        self.bits = None
        self.number_var = tk.StringVar(self, value=str(self.value))
        self.number_input = tk.Entry(self, textvariable=self.number_var, state=(tk.DISABLED if locked else tk.NORMAL))
        self.number_input.bind("<Return>", self.number_update)
        self.number_input.pack()
        if bit_size <= 16:
            self.bit_frame = tk.Frame(self)
            self.bits = []
            for i in range(bit_size):
                self.bits.append(tk.IntVar())
                c = tk.Checkbutton(self.bit_frame, variable=self.bits[-1], command=self.bits_update,
                                   state=(tk.DISABLED if locked else tk.NORMAL))
                y = i // 8
                x = 8 - i % 8
                c.grid(row=y, column=x)
            self.bit_frame.pack()

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value = value % 2 ** self.bit_size
        self.number_var.set(str(value))
        if self.bits is not None:
            for i, b in enumerate(self.bits):
                b.set(bool(value & 2 ** i))

    def number_update(self, *args):
        try:
            v = int(literal_eval(self.number_var.get()))
        except (ValueError, SyntaxError):
            pass
        else:
            self.value = v

    def bits_update(self, *args):
        self.value = sum(2 ** i * var.get() for i, var in enumerate(self.bits))


class InteractiveTester(tk.Frame):
    def __init__(self, master, gate: LogicNodeType):
        super(InteractiveTester, self).__init__(master)
        self.current_state = gate.create_state()
        self.state_history = []
        self.gate = gate
        self.inputs = {}
        for i, (name, inp) in enumerate(gate.inputs.items()):
            self.inputs[name] = bits = BitsInput(self, name, inp.bits)
            bits.grid(row=i, column=1)

        gate_button = tk.Button(self, text=gate.name, command=self.evaluate)
        gate_button.grid(row=1, column=2)
        self.outputs = {}
        for i, (name, out) in enumerate(gate.outputs.items()):
            self.outputs[name] = bits = BitsInput(self, name, out.bits)
            bits.grid(row=i, column=3)

    def evaluate(self, *args):
        inputs = {name: v.value for name, v in self.inputs.items()}
        new_state, outputs, _ = self.gate.calculate(self.current_state, **inputs)
        if new_state is not None:
            self.state_history.append(self.current_state)
        self.current_state = new_state
        for name, val in outputs.items():
            self.outputs[name].value = val


def main(cmdline):
    parser = argparse.ArgumentParser()
    parser.add_argument("main_gate", action="store")
    ns = parser.parse_args(cmdline)
    components = load_all_components((Path(__file__).parent / "components"))
    if ns.main_gate.endswith(".spec"):
        try:
            ns.main_gate = get_name_of_component(Path(ns.main_gate))
        except LarkError:
            raise ValueError(f"Couldn't find name of component in file {ns.main_gate}")
    gate = components[ns.main_gate]
    pprint(gate.execution_order)
    root = tk.Tk()
    t = InteractiveTester(root, gate)
    t.pack()
    root.mainloop()


if __name__ == '__main__':
    main(sys.argv[1:])
    # main((r"AND_2W16",))
