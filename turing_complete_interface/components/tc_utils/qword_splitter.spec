name: TC_QWORD_SPLITTER

inputs: in[64]

outputs: r0[8], r1[8], r2[8], r3[8], r4[8], r5[8], r6[8], r7[8]

components:

wires: {
    in[0:8] -> r0,
    in[8:16] -> r1,
    in[16:24] -> r2,
    in[24:32] -> r3,
    in[32:40] -> r4,
    in[40:48] -> r5,
    in[48:56] -> r6,
    in[56:64] -> r7,
}