name: OR_1W8
inputs: in[8]
outputs: out
components: or1:OR_1W4, or2:OR_1W4, or3:OR_2W1

wires: {
    in[0:4] -> or1.in,
    in[4:8] -> or2.in,

    or1.out -> or3.a,
    or2.out -> or3.b,
    or3.out -> out,

}