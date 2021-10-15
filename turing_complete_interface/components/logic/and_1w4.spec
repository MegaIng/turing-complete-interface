name: AND_1W4
inputs: in[4]
outputs: out
components: and1:AND_2W1, and2:AND_2W1, and3:AND_2W1

wires: {
    in[0] -> and1.a,
    in[1] -> and1.b,

    in[2] -> and2.a,
    in[3] -> and2.b,

    and1.out -> and3.a,
    and2.out -> and3.b,
    and3.out -> out,

}