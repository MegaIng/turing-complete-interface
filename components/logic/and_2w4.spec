name: AND_2W4
inputs: a[4], b[4]
outputs: out[4]
components: and1:AND_2W1, and2:AND_2W1, and3:AND_2W1, and4:AND_2W1

wires: {
    a[0] -> and1.a,
    b[0] -> and1.b,
    and1.out -> out[0],

    a[1] -> and2.a,
    b[1] -> and2.b,
    and2.out -> out[1],

    a[2] -> and3.a,
    b[2] -> and3.b,
    and3.out -> out[2],

    a[3] -> and4.a,
    b[3] -> and4.b,
    and4.out -> out[3],
}