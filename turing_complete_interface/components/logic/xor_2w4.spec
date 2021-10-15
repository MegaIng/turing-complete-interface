name: XOR_2W4
inputs: a[4], b[4]
outputs: out[4]
components: xor_w1:XOR_2W1, xor2:XOR_2W1, xor3:XOR_2W1, xor4:XOR_2W1

wires: {
    a[0] -> xor_w1.a,
    b[0] -> xor_w1.b,
    xor_w1.out -> out[0],

    a[1] -> xor2.a,
    b[1] -> xor2.b,
    xor2.out -> out[1],

    a[2] -> xor3.a,
    b[2] -> xor3.b,
    xor3.out -> out[2],

    a[3] -> xor4.a,
    b[3] -> xor4.b,
    xor4.out -> out[3],
}