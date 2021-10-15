name: NOT_1W16
inputs: in[16]
outputs: out[16]
components: not1:NOT4, not2:NOT4, not3:NOT4, not4:NOT4

wires: {
    in[0:4] -> not1.in,
    not1.out -> out[0:4],

    in[4:8] -> not2.in,
    not2.out -> out[4:8],

    in[8:12] -> not3.in,
    not3.out -> out[8:12],

    in[12:16] -> not4.in,
    not4.out -> out[12:16],
}