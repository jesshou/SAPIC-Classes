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

Rule: when a fragment's own shared secret is superseded this way, its
`new` must not survive in the combined `process:` block. A `new` that
nothing in the final `Client`/`Server` bodies (and no role parameter)
references is dead and must be deleted, not carried over from the
source fragment:

    tamarin-prover / validator: `new psk` in process: is not passed
    into Client/Server (let macros cannot see enclosing process names)

Wrong (`symmetric_encryption_decryption`'s own `psk` copied over
unused, even though its `senc`/`sdec` calls were rewritten to key on
`dhZ` from the earlier DH exchange):

    let Client() = ... let dhZ = ePKs^eKc in ... out(senc(mC, dhZ)) ...
    let Server() = ... let dhZ = ePKc^eKs in ... let mC = sdec(xencC, dhZ) in ...
    process:
    new psk;
    ( !Client() | !Server() )

Right (the dead `new psk;` is dropped once `dhZ` replaces it
everywhere `psk` used to appear):

    let Client() = ... let dhZ = ePKs^eKc in ... out(senc(mC, dhZ)) ...
    let Server() = ... let dhZ = ePKc^eKs in ... let mC = sdec(xencC, dhZ) in ...
    process:
    ( !Client() | !Server() )

Before finalizing, check every `new` in `process:` appears either in
a `Client(...)`/`Server(...)` parameter list or somewhere in a role
body. If it appears in neither, remove that `new` line.
