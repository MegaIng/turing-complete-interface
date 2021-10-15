name: AND_2W8
inputs: a[8], b[8]
outputs: out[8]
components: and_2w1:AND_2W4, and2:AND_2W4

wires: {
    a[0:4] -> and_2w1.a,
    b[0:4] -> and_2w1.b,
    and_2w1.out -> out[0:4],

    a[4:8] -> and2.a,
    b[4:8] -> and2.b,
    and2.out -> out[4:8],
}