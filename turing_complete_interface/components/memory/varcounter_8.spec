name: VARCOUNTER_8

inputs: ?save, ?in[8], ?delta[8]
outputs: out[8]

components: adder: ADDER_2W8, reg: REGISTER_8, _: CONST, mux: MUX_2W8

wires: {

    save -> mux.control,
    adder.out -> mux.a,
    in -> mux.b,

    _.true -> reg.save,
    mux.out -> reg.value,

    reg.out -> adder.a,
    _.false -> adder.carry_in,
    delta -> adder.b,

    reg.out -> out

}