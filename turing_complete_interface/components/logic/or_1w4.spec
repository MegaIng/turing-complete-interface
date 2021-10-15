name: OR_1W4
inputs: in[4]
outputs: out
components: or1:OR_2W1, or2:OR_2W1, or3:OR_2W1

wires: {
    in[0] -> or1.a,
    in[1] -> or1.b,

    in[2] -> or2.a,
    in[3] -> or2.b,

    or1.out -> or3.a,
    or2.out -> or3.b,
    or3.out -> out,

}