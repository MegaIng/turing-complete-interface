name: TC_DEMUX_2

inputs: control
outputs: a, b

components: not: NOT_1W1

wires: {
    control -> not.in, not.out -> a,
    control -> b,
}

