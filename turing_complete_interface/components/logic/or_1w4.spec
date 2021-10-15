name: OR_1W4
inputs: in[4]
outputs: out
components: or1:OR_2W1, or2:OR_2W1, or3:OR_2W1

wires: {
    in[0] -> or1.0,
    in[1] -> or1.1,

    in[2] -> or2.0,
    in[3] -> or2.1,

    or1.out -> or3.0,
    or2.out -> or3.1,
    or3.out -> out,

}