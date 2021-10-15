name: MUX_2W8

inputs: control, a[8], b[8]

outputs: out[8]

components: mux1: MUX_2W4, mux2: MUX_2W4

wires: {
    control -> mux1.control,
    control -> mux2.control,

    a[0:4] -> mux1.a,
    b[0:4] -> mux1.b,

    a[4:8] -> mux2.a,
    b[4:8] -> mux2.b,

    mux1.out -> out[0:4],
    mux2.out -> out[4:8],
}