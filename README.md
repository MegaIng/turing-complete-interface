# turing_complete_interface

Is a library to interface with the circuits created in the game [Turing Complete](https://turingcomplete.game/)

The library currently allows viewing and stepping circuits.

This is in preparation for work to be able to compile those circuits to "standalone" programs.

## Installation

Requires Python3.10

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install turing_complete_interface.

```bash
pip install git+https://github.com/MegaIng/logic_nodes.git
```

Note that when you get error messages you can try to do `pip uninstall lark-parser lark`, followed by `pip install git+https://github.com/lark-parser/lark`

## Usage
```bash
python -m turing_complete_interface.circuit_viewer [-l <level_name>] [-s <save_name>] [-a <assembly_name>]
```
When you don't pass some of ``-l``, `-s`, ``-a``, a prompt with autocomplete will appear in the terminal (will not ask for assembly on non architecture levels)


Example:

```
python -m turing_complete_interface.circuit_viewer -l "architecture" -s "OVERTURE" -a "circumference/example"
```

Will execute your implementation of OVERTURE with the circumference program.

This will open two windows:

A pygame window displaying the circuit layout and a tkinter window allowing you to modify the inputs and easily see the output values off your circuit.

Pressing space in the pygame window will do one simulation step, holding in down multiple. WARNING: Currently a step is slow, and holding Space down will slow down the FPS. Press Enter to view a placed AsciiScreen/FastBotTurtle. Keyboard also works.


### FastBotTurtle

Something that is currently not in the game. This mode allows you to run a program with FastBOT controls, that draws a line behind it like a turtle drawing library would. Just add `--fast-bot-turtle` to the command line. Assumes you have an architecture level loaded.

### From verilog

It is possible to load a circuit from a verilog file, if the file was compiled and flattened via YoSys with the techlib by NotEdward on discord (links coming soon).

To view such a generated circuit use:

````bash
python -m turing_complete_interface.circuit_viewer -v <verilog file> -l <level name>
````

level name is not required, but if passed it is used to correctly set the dimensions of the output circuit space.
(Future plan is to also include IO information.)

To not view it and instead replace a save you have with the circuit use this:

````bash
python -m turing_complete_interface.from_verilog <verilog file> -l <level name> -s <save name>
````

If ``-s`` is not present a name is generated based on the input file name.

Probably the most common level to target (and probably the only safe one right now) is the Component Factory:

````bash
python -m turing_complete_interface.from_verilog <verilog file> -l component_factory
````


## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.


## License
[MIT](https://choosealicense.com/licenses/mit/)
