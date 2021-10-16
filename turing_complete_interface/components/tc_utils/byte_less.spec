name: BYTE_LESS

inputs: a[8], b[8]

outputs: signed, unsigned

components: less_u: BYTE_LESS_U, less_s: BYTE_LESS_S

wires: {
    a -> less_u.1,
    b -> less_u.2,
    a -> less_s.1,
    b -> less_s.2,

    less_u -> unsigned,
    less_s -> signed,
}

