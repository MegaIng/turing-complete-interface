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

Example:

```
python -m turing_complete_interface.circuit_viewer -l "architecture" -a "OVERTURE" -a "circumference/example"
```

Will execute your implementation of OVERTURE with the circumference program.

This will open two windows:

A pygame window displaying the circuit layout and a tkinter window allowing you to modify the inputs and easily see the output values off your circuit.

Pressing space in the pygame window will do one simulation step, holding in down multiple. WARNING: Currently a step is slow, and holding Space down will freeze the windows. Press Enter to view a placed AsciiScreen. Keyboard also works.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit/)
