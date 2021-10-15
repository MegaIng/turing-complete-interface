name: NOT4
inputs: in[4]
outputs: out[4]
components: not1:NOT_1W1, not2:NOT_1W1, not3:NOT_1W1, not4:NOT_1W1

wires: {
    in[0] -> not1.in,
    not1.out -> out[0],

    in[1] -> not2.in,
    not2.out -> out[1],

    in[2] -> not3.in,
    not3.out -> out[2],

    in[3] -> not4.in,
    not4.out -> out[3],
}