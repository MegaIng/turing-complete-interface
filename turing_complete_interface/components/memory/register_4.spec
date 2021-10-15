name: REGISTER_4

inputs: save, ?in[4]
outputs: out[4]

components: reg0: REGISTER_1, reg1: REGISTER_1, reg2: REGISTER_1, reg3: REGISTER_1

wires: {
    save -> reg0.save,
    save -> reg1.save,
    save -> reg2.save,
    save -> reg3.save,

    in[0] -> reg0.in,
    in[1] -> reg1.in,
    in[2] -> reg2.in,
    in[3] -> reg3.in,

    reg0.out -> out[0],
    reg1.out -> out[1],
    reg2.out -> out[2],
    reg3.out -> out[3],
}