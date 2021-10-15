name: SWITCH_1W4

inputs: control, in[4]

outputs: out[4]

components: and1:AND_2W1, and2:AND_2W1, and3:AND_2W1, and4:AND_2W1

wires: {
    control -> and1.a,
    in[0] -> and1.b,
    and1.out -> out[0],

    control -> and2.a,
    in[1] -> and2.b,
    and2.out -> out[1],

    control -> and3.a,
    in[2] -> and3.b,
    and3.out -> out[2],

    control -> and4.a,
    in[3] -> and4.b,
    and4.out -> out[3],
}