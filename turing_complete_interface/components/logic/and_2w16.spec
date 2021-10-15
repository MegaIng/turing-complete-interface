name: AND_2W16
inputs: a[16], b[16]
outputs: out[16]
components: and_2w1:AND_2W4, and2:AND_2W4, and3:AND_2W4, and4:AND_2W4

wires: {
    a[0:4] -> and_2w1.a,
    b[0:4] -> and_2w1.b,
    and_2w1.out -> out[0:4],

    a[4:8] -> and2.a,
    b[4:8] -> and2.b,
    and2.out -> out[4:8],

    a[8:12] -> and3.a,
    b[8:12] -> and3.b,
    and3.out -> out[8:12],

    a[12:16] -> and4.a,
    b[12:16] -> and4.b,
    and4.out -> out[12:16],
}