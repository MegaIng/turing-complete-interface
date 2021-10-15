name: SWITCH_1W8

inputs: control, in[8]

outputs: out[8]

components: and:AND_2W8

wires: {
    control -> and.a[0],
    control -> and.a[1],
    control -> and.a[2],
    control -> and.a[3],
    control -> and.a[4],
    control -> and.a[5],
    control -> and.a[6],
    control -> and.a[7],
    in -> and.b,
    and.out -> out,
}