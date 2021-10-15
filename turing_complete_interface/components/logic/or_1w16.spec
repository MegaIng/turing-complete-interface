name: OR_1W16
inputs: in[16]
outputs: out
components: or1:OR_1W4, or2:OR_1W4, or3:OR_1W4, or4:OR_1W4, or5:OR_1W4

wires: {
    in[0:4] -> or1.in,
    in[4:8] -> or2.in,

    in[8:12] -> or3.in,
    in[12:16] -> or4.in,

    or1.out -> or5.in[0],
    or2.out -> or5.in[1],
    or3.out -> or5.in[2],
    or4.out -> or5.in[3],
    or5.out -> out,

}