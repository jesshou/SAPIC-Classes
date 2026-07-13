# REWRITE INSTRUCTIONS: combining class fragments

Rule: if a `new` value is a parameter shared by both `Client` and
`Server` in a fragment (e.g. `let Server(psk) = ...`), keep it as a
parameter on both merged roles and hoist its `new` into the combined
theory's single `process:` block. Never generate it inside only one
role — the other role's reference will be unbound:

    tamarin-prover: Process not well-formed: The variable(s) psk are not bound.

Wrong (psk only bound in Client, unbound in Server):

    let Client() = ... new psk; out(senc(mC, psk)) ...
    let Server() = ... let mC = sdec(xencC, psk) in ...   // unbound
    process:
    ( !Client() | !Server() )

Right (psk created once, passed to both):

    let Client(psk) = ... out(senc(mC, psk)) ...
    let Server(psk) = ... let mC = sdec(xencC, psk) in ...
    process:
    new psk;
    ( !Client(psk) | !Server(psk) )

Private values (used by only one role: long-term keys, ephemeral DH
exponents, that role's own nonce) stay as `new` inside that role's
own `let` — no parameter, no hoisting.

If combining classes would otherwise introduce two unrelated shared
secrets that should be the same value (e.g. a DH-derived `dhZ` meant
to serve as the symmetric key for a later data-exchange class),
reuse the earlier bound variable as the later class's parameter
instead of adding a second `new`.
