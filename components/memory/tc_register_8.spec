name: TC_REGISTER_8

inputs: load, save, ?value[8]
outputs: out[8]

components: reg0: REGISTER_4, reg1: REGISTER_4, switch0: SWITCH_1W4, switch1: SWITCH_1W4

wires: {
    save -> reg0.save,
    save -> reg1.save,

    value[0:4] -> reg0.in,
    value[4:8] -> reg1.in,

    reg0.out -> switch0.in,
    reg1.out -> switch1.in,

    load -> switch0.control,
    load -> switch1.control,

    switch0.out -> out[0:4],
    switch1.out -> out[4:8],
}