# SAPIC+ Classes

A library of small, self-contained SAPIC+ building blocks for constructing and analyzing security protocols in [Tamarin](https://tamarin-prover.com/). Each file models one protocol step in isolation — key generation, message transport, hashing-based liveness checks, and so on — with its own executability and security lemmas. The idea is to compose these classes (copy/adapt the relevant `let` processes) into a full protocol model rather than writing every protocol from scratch.

## Structure

Files are organized by the phase of a protocol they belong to, numbered in the order they'd typically appear in a composed model:

```
protocol-code/
  1) Startup/        - key/parameter generation, initial setup
  2) DataTransfer/    - message exchange primitives (encryption, hashing, ...)
  3) Cleanup/         - session teardown, key revocation (placeholder)
protocol-executability-lemmas/
                      - shared/reusable executability lemmas (placeholder)
```

### 1) Startup

- **`setup.spthy`** — Bare-minimum skeleton: empty `Client()`/`Server()` processes wired into `!( !Client() | !Server() )`. Use this as the starting scaffold for a new protocol model before filling in the roles.
- **`asymmetric_key_generation.spthy`** — Client and Server each generate a long-term asymmetric keypair (`asymmetric-encryption` builtin) and announce their public key via `ClientInit`/`ServerInit` events. Includes a `setup_executable` sanity lemma proving the process can actually run.

### 2) DataTransfer

- **`asymmetric_encryption.spthy`** — Client transports a fresh session key `k` to the Server confidentially by encrypting it under the Server's public key (`aenc`/`adec`). Models long-term key compromise explicitly via an `LtkReveal` event/channel per party, and proves:
  - `Client_session_key_secrecy` — `k` stays secret unless the Server's long-term key was revealed.
  - `Client_session_key_honest_setup` — an honest run (no reveal) is reachable at all.
- **`hashing.spthy`** — Client and Server share a key `k` (modeled as scoped over both roles, i.e. established out-of-band). Server proves liveness/possession of `k` by sending `h(k)`; Client checks the hash. Models compromise via a `KeyReveal` event/channel, and proves:
  - `Client_auth` — a Client only accepts `h(k)` if the Server actually answered with it, or `k` was revealed beforehand.
  - `Client_session_key_honest_setup` — an honest (non-revealed) accept is reachable.

### 3) Cleanup

Placeholder for teardown steps (e.g. key/session revocation, explicit destroy events). Not yet populated.

### protocol-executability-lemmas

Placeholder for lemma patterns intended to be reused across models (e.g. generic `exists-trace` sanity checks). Not yet populated.

## Conventions used across these files

- **Roles as `let` processes.** Each party is a parameterized `let Client(...) = ...` / `let Server(...) = ...` process, instantiated in a top-level `process:` block, typically under replication (`!`) for unbounded sessions.
- **Compromise modeled explicitly.** Long-term secrets aren't just left in the model — files that use them expose a companion `LtkReveal(pk)` / `KeyReveal(k)` event and channel (`out(...)`), so security lemmas can state guarantees of the form "secret holds *unless* this specific key was revealed" rather than an unconditional (and false) secrecy claim.
- **Two-lemma pattern.** Most files pair a negative/implication lemma (secrecy or authentication guarantee) with an `exists-trace` lemma showing an honest run satisfying the guarantee is actually reachable — this catches vacuously true lemmas.
- **Minimal bodies.** Processes only contain what the class is meant to demonstrate (e.g. `setup.spthy` has empty `0` bodies) — flesh them out when composing into a full protocol.

## Using these classes

1. Start from `1) Startup/setup.spthy` (or the key-generation variant) as your process skeleton.
2. Splice in the `let` bindings from the `DataTransfer` class(es) your protocol needs, threading key material between roles as parameters.
3. Add `Cleanup` steps once populated, or write your own teardown events following the reveal-event convention above.
4. Run with:
   ```
   tamarin-prover --prove path/to/file.spthy
   ```
   or open interactively with:
   ```
   tamarin-prover interactive path/to/file.spthy
   ```
