from turing_complete_interface.scripts import *

select_level("component_factory")

# circuit = load_circuit("LUTs/Templates/ExampleDoubleEntry")
# show_circuit(circuit, True)

lut = lut_from_bytes(b"0123456789ABCDEFFEDCBA9876543210" * 8 * 2, 9, 8)
lut.truth.reduce_dupes()
print(lut)

gen = CompactTruthTableGenerator(
    Pattern.from_circuit(load_circuit("LUTs/Templates/ExampleInput"), {
        "pos": FilterPins(SortPins(FromGates(GatesByKind("ByteSplitter"), outputs=True)), lambda p, _: p[1] <= 0),
        "neg": FilterPins(SortPins(FromGates(GatesByKind("ByteSplitter"), outputs=True)), lambda p, _: p[1] > 0),

    }),
    Pattern.from_circuit(load_circuit("LUTs/Templates/ExampleSingleEntry"), {
        "ins": FromGates(CustomByName("In14"), inputs=True),
        "out": FromGates(CustomByName("Combine1"), outputs=True)
    }),
    Pattern.from_circuit(load_circuit("LUTs/Templates/ExampleDoubleEntry"), {
        "a": FromGates(CustomByName("In14"), inputs=True),
        "b": FromGates(CustomByName("In14R"), inputs=True),
        "out": FromGates(CustomByName("Combine2"), outputs=True)
    }),
    Pattern.from_circuit(load_circuit("LUTs/Templates/ExampleExpand"), {
        "values": Concatenate([
            SortPins(FromGates(CustomByName("Expand12 chain"), inputs=True,
                               filter=lambda _, pin: isinstance(pin.name, int) or pin.name.isdigit()), "xy"),
            SortPins(
                FromGates(CustomByName("Expand14"), inputs=True,
                          filter=lambda _, pin: isinstance(pin.name, int) or pin.name.isdigit()), "xy"),
        ]),
        "prev": FromGates(CustomByName("Or64"), inputs=True, filter=lambda _, pin: pin.name == "A"),
        "next": FromGates(CustomByName("Or64"), outputs=True)
    }),
    Pattern.from_circuit(load_circuit("LUTs/Templates/ExampleOutput"), {
        "prev": FromGates(GatesByKind("OutputQword"), inputs=True)
    })
)
circuit = gen.generate(lut.truth)

show_circuit(circuit, True)

save_custom_component(circuit, "LUTs/TestGenerated")
