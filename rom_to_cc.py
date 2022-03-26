#!/usr/bin/env python3
from typing import Iterator
from turing_complete_interface.scripts import *
import argparse


def read_file(file_name: str, word_size: int, dont_cares: list[int]) -> list[int]:
    with open(file_name, "rb") as f:
        data = f.read()
    data = [data[i:i + word_size] for i in range(0, len(data), word_size)]
    data = [int.from_bytes(b, "little") for b in data]
    if dont_cares:
        data = [None if b in dont_cares else b for b in data]
    return data


def xnor_lfsr(width: int) -> Iterator[int]:
    result = 0
    mask = 1 << (width - 1)
    yield 0
    while True:
        next_r = (result << 1)
        xor = (next_r ^ result) & mask
        result = next_r & (2 ** width - 1)
        if xor == 0:
            result ^= 1
        yield result


def apply_lfsr(lfsr_size: int, data: list[int]) -> list[int]:
    lfsr = xnor_lfsr(lfsr_size)
    positions = [next(lfsr) for _ in range(2 ** lfsr_size)]
    for i, p in enumerate(positions):
        if positions.index(p) < i:
            print(f"Warning: LFSR only has {i} unique values. Will attempt to pack data.")
            del positions[i:]
            break
    mask = 2 ** lfsr_size - 1
    data3: list[int | None] = [None] * len(data)
    for i, d in enumerate(data):
        if d is None:
            continue
        assert i & mask < len(positions), f"Unable to pack data into this LFSR at index {i}, {i & mask} >= {len(positions)}"
        p = positions[i & mask] | (i & ~mask)
        data3[p] = d
    return data3


def decoding_template(out_bits: int) -> tuple[str, list[str]]:
    if out_bits <= 16:
        return "LUTs/Templates/Expand16", ["Expand16D"]
    elif out_bits <= 32:
        return "LUTs/Templates/Expand32", ["Expand16A", "Expand16D"]
    elif out_bits <= 64:
        return "LUTs/Templates/Expand64", ["Expand16A", "Expand16B", "Expand16C", "Expand16D"]
    else:
        raise f"Too many outputs: {out_bits}, no template available"


def output_template(out_bits: int) -> tuple[str, str]:
    if out_bits <= 1:
        return "LUTs/Templates/Output1", "Output1"
    elif out_bits <= 8:
        return "LUTs/Templates/Output8", "Output8"
    elif out_bits <= 64:
        return "LUTs/Templates/Output64", "Output64"
    else:
        raise f"Too many outputs: {out_bits}, no template available"


def input_template(in_bits: int, inverted_inputs: bool) -> tuple[str, str, str]:
    if in_bits <= 8 and inverted_inputs:
        return "LUTs/Templates/Input8-Inverted", "ByteSplitter", "ByteSplitter"
    elif in_bits <= 32 and inverted_inputs:
        return "LUTs/Templates/Input32-Inverted", "ByteSplitter", "ByteSplitter",
    elif in_bits <= 8:
        return "LUTs/Templates/Input8", "ByteSplitter", "Not"
    elif in_bits <= 32:
        return "LUTs/Templates/Input32", "ByteSplitter", "ByteSplitter"
    else:
        raise f"Too many inputs: {in_bits}, no template available"


def ttgen(in_bits, inverted_inputs, out_bits) -> CompactTruthTableGenerator:
    input_circuit, kind_pos, kind_neg = input_template(in_bits, inverted_inputs)
    input_pattern = Pattern.from_circuit(load_circuit(input_circuit), {
        "pos": FilterPins(SortPins(FromGates(GatesByKind(kind_pos), outputs=True), "xy"), lambda p, _: p[1] <= 0),
        "neg": FilterPins(SortPins(FromGates(GatesByKind(kind_neg), outputs=True), "xy"), lambda p, _: p[1] > 0),
    })
    single_entry_pattern = Pattern.from_circuit(load_circuit("LUTs/Templates/EntrySingle"), {
        "ins": FromGates(CustomByName("Or14"), inputs=True),
        "out": FromGates(CustomByName("Combine-NOR"), outputs=True)
    })
    double_entry_pattern = Pattern.from_circuit(load_circuit("LUTs/Templates/EntryDouble"), {
        "a": FromGates(CustomByName("Or14"), inputs=True),
        "b": FromGates(CustomByName("Or14R"), inputs=True),
        "out": FromGates(CustomByName("Combine-NAND"), outputs=True)
    })
    decoding_circuit, decoding_gates = decoding_template(out_bits)
    decoding_pattern = Pattern.from_circuit(load_circuit(decoding_circuit), {
        "values": Concatenate([
            SortPins(FromGates(CustomByName(gate), inputs=True,
                               filter=lambda _, pin: isinstance(pin.name, int) or pin.name.isdigit()), "xy")
            for gate in decoding_gates
        ]),
        "prev": FromGates(GatesByKind("QwordOr"), inputs=True, filter=lambda _, pin: pin.name == "a"),
        "next": FromGates(GatesByKind("QwordOr"), outputs=True)
    })
    output_circuit, output_kind = output_template(out_bits)
    output_pattern = Pattern.from_circuit(load_circuit(output_circuit), {
        "prev": FromGates(GatesByKind(output_kind), inputs=True)
    })
    return CompactTruthTableGenerator(
        input_pattern,
        single_entry_pattern,
        double_entry_pattern,
        decoding_pattern,
        output_pattern)


def rom_to_cc(data: list[int],
              in_bits: int,
              inverted_inputs: bool,
              lfsr_size: int,
              output_file_name: str,
              out_bits: int,
              layout: LevelLayout = None,
              print_lut: bool = False):
    # Reorder data for LFSR counter
    if lfsr_size > 0:
        data = apply_lfsr(lfsr_size, data)
    # Create the LUT
    lut = lut_from_bytes(data, in_bits, out_bits)
    lut.truth.prune_zeros()
    lut.truth.reduce_dupes()
    if print_lut:
        print(lut)

    select_level("component_factory")
    gen = ttgen(in_bits, inverted_inputs, out_bits)
    circuit = gen.generate(lut.truth, layout=layout)

    try:
        old = load_circuit(output_file_name)
        print(f"Found {output_file_name} {old.save_version}")
        circuit.save_version = old.save_version
    except FileNotFoundError:
        pass
    circuit.delay = 2 if inverted_inputs else 4
    save_custom_component(circuit, output_file_name)
    print(f"Wrote to {output_file_name}, LUT cost is {circuit.nand}/{circuit.delay}")


def main():
    parser = argparse.ArgumentParser(description="""
                                     example: %(prog)s microcode.bin 4 9 19 SAP-Microcode

                                     Used to convert binary files to LUT components for Turing Complete
                                     """)
    parser.add_argument('in_file',
                        help='Input ROM file')
    parser.add_argument('in_alignment',
                        type=int,
                        help='Input ROM entry alignment, in bytes')
    parser.add_argument('in_bits',
                        type=int,
                        help='Input width, in bits')
    parser.add_argument('out_bits',
                        type=int,
                        help='Output width, in bits')
    parser.add_argument('out_file',
                        help='Output component name')
    parser.add_argument('-i', '--inverted-inputs',
                        action='store_true',
                        help='Inverted inputs available')
    parser.add_argument('-p', '--prune',
                        type=int,
                        action="append",
                        default=[0],
                        help="Prune this value from the LUT (don't cares)")
    parser.add_argument('-n', '--disable-prune-zero',
                        action='store_true',
                        help="Disable pruning zero from the LUT (don't cares)")
    parser.add_argument('-l', '--lfsr-size',
                        type=int,
                        default=0,
                        help='Encode LUT for XNOR LFSR lookup')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase log level')
    parser.add_argument('-V', '--version',
                        action='version',
                        version='%(prog)s 1.0')
    options = parser.parse_args()
    if options.disable_prune_zero:
        options.prune.remove(0)
    data = read_file(
        options.in_file,
        options.in_alignment,
        options.prune)
    rom_to_cc(
        data,
        options.in_bits,
        options.inverted_inputs,
        options.lfsr_size,
        options.out_file,
        options.out_bits,
        None,
        options.verbose > 0)


if __name__ == '__main__':
    main()
