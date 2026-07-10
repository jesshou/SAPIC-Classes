# GENERAL SAPIC+ INSTRUCTIONS

## `new` scope + `let` macro params

- `let ROLE(...) = ...` macros do NOT see names from the enclosing
  `process:` block, even if nested inside it. Any shared value must
  be passed as an explicit parameter — else:
  `Process not well-formed: The variable(s) k are not bound.`
- Shared value (common key, channel name) → `new` in `process:`,
  passed into each role as a parameter:

      let Client(k) = new m; out(senc(m, k))
      let Server(k) = in(x); let m = sdec(x, k) in ...

      process:
      new k;
      ( !Client(k) | !Server(k) )

- Private value (long-term key) → `new` inside the role's own `let`,
  no parameter needed:

      let Client() = new ~ltkA; let pkA = pk(~ltkA) in ...

## Channels

Channel = first arg to `in(...)`/`out(...)`. Shared channel name →
declare with `new` in `process:`, pass to roles like any shared value:

    let Client(c) = new cr; out(c, <'client_hello', cr>)
    let Server(c) = in(c, <'client_hello', cr>)

    process:
    new c;
    ( !Client(c) | !Server(c) )

No `new` → free/public constant (adversary knows it from the start).
Fine for a plain public channel; use `new` only if the channel name
itself must be secret at creation.

## Freshness

`new` = globally unique, adversary-unknown at creation. Nonce,
session ID, ephemeral key are all just `new` values, differing only
in role (anti-replay / correlation label / forward secrecy).

`~` marks fresh-sorted variables (`~n`, `~ltkA`, `~ek`) — always use
on a variable bound to `new`.
