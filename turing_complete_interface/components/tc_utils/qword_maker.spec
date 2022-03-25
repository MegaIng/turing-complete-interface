name: TC_QWORD_MAKER

inputs: r0[8], r1[8], r2[8], r3[8], r4[8], r5[8], r6[8], r7[8]

outputs: out[64]

components:

wires: {
    r0 -> in[0:8],
    r1 -> in[8:16],
    r2 -> in[16:24],
    r3 -> in[24:32],
    r4 -> in[32:40],
    r5 -> in[40:48],
    r6 -> in[48:56],
    r7 -> in[56:64],
}