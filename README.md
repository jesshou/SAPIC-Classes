# SAPIC+ Classes

A library of small, self-contained SAPIC+ building blocks for constructing and analyzing security protocols in [Tamarin](https://tamarin-prover.com/). Each file models one protocol step in isolation — key generation, a handshake message, a key-derivation step, message transport, and so on — with its own executability and (where relevant) security lemmas. The idea is to compose these classes (copy/adapt the relevant `let` processes) into a full protocol model rather than writing every protocol from scratch.

## Structure

Files are organized by the phase of a protocol they belong to, numbered in the order they'd typically appear in a composed model:

```
protocol-code/
  1) Startup/         - key/parameter generation, nonces, session IDs, initial setup
  2) DataTransfer/     - handshake messages, key exchange/derivation, authentication, message transport
  3) Cleanup/          - session teardown, key revocation
protocol-executability-lemmas/
                      - shared/reusable executability lemmas (placeholder)
```

### 1) Startup

- **`setup.spthy`** — Bare-minimum skeleton: empty `Client()`/`Server()` processes wired into `!( !Client() | !Server() )`. Use this as the starting scaffold for a new protocol model before filling in the roles.
- **`asymmetric_key_generation.spthy`** — Client and Server each generate a long-term asymmetric keypair (`asymmetric-encryption` builtin) and announce their public key via `ClientInit`/`ServerInit` events. Proves `setup_executable`/`server_setup_executable` sanity lemmas.
- **`symmetric_key_generation.spthy`** — Skeleton for protocols keyed by a shared long-term symmetric secret: a single `~psk` is generated in `process:` and threaded into empty `Client(~psk)`/`Server(~psk)` roles to fill in.
- **`nonce.spthy`** — Demonstrates the fresh-nonce pattern: `new n` plus a `ClientNonce(n)` event, proving freshness/anti-replay values are reachable (`nonce_executable`).
- **`sessionID.spthy`** — Same pattern as `nonce.spthy` but for a session/correlation identifier (`ClientSessionID`) — a bookkeeping label rather than a cryptographic value (`sessionID_executable`).

### 2) DataTransfer

**Handshake messages**
- **`client_hello.spthy`** — Client sends a fresh client-random nonce (`ClientHello`); Server receives it. Proves `exists_ClientHello`.
- **`server_hello.spthy`** — Mirror of the above: Server sends a fresh server-random nonce; Client receives it. Proves `exists_ServerHello`.

**Key exchange / derivation**
- **`diffie_hellman_ephemeral.spthy`** — Fresh (per-session) DH exchange (`diffie-hellman` builtin): each party picks a new exponent, exchanges `g^x`/`g^y`, and derives a shared key `k`. Gives forward secrecy. Proves message ordering (`server_received_client_key`, `client_received_server_key`) and `keys_match` (both sides derive the same key).
- **`diffie_hellman_static.spthy`** — Same shape but each party's exponent is a long-term static secret reused across all sessions (no forward secrecy). Proves `key_agreement_exists`.
- **`key_transport.spthy`** — Minimal key-transport primitive: Client generates a fresh key `k` and sends it encrypted under the Server's public key (`asymmetric-encryption`), no compromise modeling. Proves the exchanged key matches on both sides (`exists_trace`).
- **`HKDF.spthy`** — Derives a session key the way TLS 1.3 does: combines an ephemeral DH shared secret `Z` (forward secrecy) with a long-term PSK (implicit authentication against an unauthenticated-DH MitM) into `IKM`, then models RFC 5869 HKDF abstractly via free functions `hkdf_extract/2` and `hkdf_expand/3`. Proves `executability` and `secrecy_OKM` (the derived output keying material stays secret).

**Authentication**
- **`signature_generation_verification.spthy`** — Server signs a message (`signing` builtin) and publishes `(pk, m, sig)`; Client verifies. Proves `client_verify_exists`.
- **`asymmetric_encryption_decryption.spthy`** — Client transports a fresh session key `k` to the Server confidentially, encrypted under the Server's public key (`aenc`/`adec`). Models long-term key compromise explicitly via an `LtkReveal` event/channel per party, and proves:
  - `Client_session_key_secrecy` — `k` stays secret unless the Server's long-term key was revealed.
  - `Client_session_key_honest_setup` — an honest run (no reveal) is reachable at all.
- **`hashing.spthy`** — Client and Server share a key `k` (modeled as scoped over both roles, i.e. established out-of-band). Server proves liveness/possession of `k` by sending `h(k)`; Client checks the hash. Models compromise via a `KeyReveal` event/channel, and proves:
  - `Client_auth` — a Client only accepts `h(k)` if the Server actually answered with it, or `k` was revealed beforehand.
  - `Client_session_key_honest_setup` — an honest (non-revealed) accept is reachable.
- **`handshake_finished.spthy`** — TLS 1.3-style "Finished" step: after a DH exchange, each side computes and exchanges hash-based `finished` confirmations (`h(<'finished_client'/'finished_server', k>)`) over the derived key to authenticate the handshake before either party accepts. No lemmas yet — proves out by composition with a DH class.

**Message transport**
- **`symmetric_encryption_decryption.spthy`** — Bare symmetric transport: Client sends a fresh message under a shared key (`senc`), Server decrypts (`sdec`), no compromise modeling. Proves `decryption_exists`.
- **`application_data_exchange.spthy`** — Post-handshake bidirectional application data: Client sends a message under a shared key `k`, Server replies with its own message under the same key. Event hooks for send/receive are stubbed out (commented) for composition into a larger model; no lemmas yet.

### 3) Cleanup

- **`closing.spthy`** — Bare `Client()`/`Server()` skeleton (theory `ClientServer`) for the teardown phase, analogous to `setup.spthy`. Flesh out with explicit close/revocation events when composing.

### protocol-executability-lemmas

Placeholder for lemma patterns intended to be reused across models (e.g. generic `exists-trace` sanity checks). Not yet populated.

## Conventions used across these files

- **Roles as `let` processes.** Each party is a parameterized `let Client(...) = ...` / `let Server(...) = ...` process, instantiated in a top-level `process:` block, typically under replication (`!`) for unbounded sessions.
- **Compromise modeled explicitly where it matters.** Files that carry long-term secrets across sessions (`asymmetric_encryption_decryption.spthy`, `hashing.spthy`) expose a companion `LtkReveal(pk)` / `KeyReveal(k)` event and channel (`out(...)`), so security lemmas can state guarantees of the form "secret holds *unless* this specific key was revealed" rather than an unconditional (and false) secrecy claim. Simpler, single-purpose primitives (`key_transport.spthy`, `symmetric_encryption_decryption.spthy`, the DH classes) skip this and are meant to be wrapped with a reveal pattern by the composed model if needed.
- **Two-lemma pattern where compromise applies.** Files with a reveal event pair a negative/implication lemma (secrecy or authentication guarantee) with an `exists-trace` lemma showing an honest run satisfying the guarantee is actually reachable — this catches vacuously true lemmas. Purely structural classes (hellos, handshake finished, application data) instead just prove reachability, or leave lemmas to the composed model.
- **Minimal bodies.** Processes only contain what the class is meant to demonstrate (e.g. `setup.spthy`/`closing.spthy` have empty `0` bodies) — flesh them out when composing into a full protocol.

## Using these classes

1. Start from `1) Startup/setup.spthy` (or a key-generation variant) as your process skeleton.
2. Splice in the `let` bindings from the `DataTransfer` class(es) your protocol needs — hellos, a key-exchange/derivation class, then transport/authentication classes — threading key material and nonces between roles as parameters.
3. Add `3) Cleanup/closing.spthy` (or your own teardown events) once the session needs an explicit close, following the reveal-event convention above if long-term secrets are involved.
4. Run with:
   ```
   tamarin-prover --prove path/to/file.spthy
   ```
   or open interactively with:
   ```
   tamarin-prover interactive path/to/file.spthy
   ```
</content>
