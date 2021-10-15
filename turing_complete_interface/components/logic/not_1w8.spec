name: NOT_1W8
inputs: in[8]
outputs: out[8]
components: not1:NOT4, not2:NOT4

wires: {
    in[0:4] -> not1.in,
    not1.out -> out[0:4],

    in[4:8] -> not2.in,
    not2.out -> out[4:8],
}