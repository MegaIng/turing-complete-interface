name: AND_1W16
inputs: in[16]
outputs: out
components: and1:AND_1W4, and2:AND_1W4, and3:AND_1W4, and4:AND_1W4, and5:AND_1W4

wires: {
    in[0:4] -> and1.in,
    in[4:8] -> and2.in,

    in[8:12] -> and3.in,
    in[12:16] -> and4.in,

    and1.out -> and5.in[0],
    and2.out -> and5.in[1],
    and3.out -> and5.in[2],
    and4.out -> and5.in[3],
    and5.out -> out,

}