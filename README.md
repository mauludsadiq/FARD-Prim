# FARD Prim

**FARD Prim** is the FARD-first foundation for rebuilding ORGNTR inside FARD.

The Rust repository `COMPILER---ORGNTR` has reached a concrete native-code milestone:

```text
cargo clean
cargo build -p orgntr_rt --target x86_64-apple-darwin
cargo build -p orgntr_cli
cargo run -p orgntr_cli
RT=target/x86_64-apple-darwin/debug/liborgntr_rt.a
cc -arch x86_64 -o run host.c out.o "$RT"
./run
```

Observed result:

```text
wrote out.o
2
```

And the object file now carries modern Mach-O platform metadata:

```text
otool -l out.o | rg -n "LC_BUILD_VERSION|LC_VERSION_MIN"
39:      cmd LC_BUILD_VERSION
```

That proves the current Rust implementation can emit a valid x86_64 Mach-O object, link it against the ORGNTR runtime, execute it, and preserve the platform load command.

This repo moves the **compiler truth layer** into FARD.

---

## What this repo contains

```text
src/orgntr_prim/ocir.fard          OCIR constructors and digest
src/orgntr_prim/verify.fard        OCIR verifier
src/orgntr_prim/hash.fard          trust hashing helpers
src/orgntr_prim/target.fard        deterministic target descriptor
src/orgntr_prim/run_gate.fard      branch-gate OCIR builder/report
programs/branch_gate.fard          executable gate program
tests/test_ocir_verify.fard        verifier tests
tests/test_branch_gate.fard        branch-gate trust tests
docs/FARD_TO_ORGNTR.md             transition plan from Rust ORGNTR to pure FARD
```

This is not the full FARD object emitter yet. It is the required pure-FARD semantic layer before object emission can move out of Rust.

---

## Where we are now

Current Rust ORGNTR proof:

```text
OCIR branch gate -> x86_64 Mach-O object -> link -> run -> 2
```

Current FARD Prim layer:

```text
FARD OCIR model
FARD OCIR verifier
FARD OCIR digest
FARD trust record
FARD target descriptor
FARD branch gate report
```

The authority transition is:

```text
Rust as compiler authority
```

to:

```text
FARD as compiler authority
Rust as temporary object-emission comparison backend
```

---

## Run

```bash
fardrun run --program programs/branch_gate.fard --out out/branch_gate
cat out/branch_gate/result.json
```

Expected semantic shape:

```json
{
  "verified": true,
  "entry": "fard_main",
  "ocir_hash": "sha256:...",
  "target": "x86_64-apple-darwin",
  "expected_runtime_value": 2
}
```

---

## Tests

```bash
fardrun test --program tests/test_ocir_verify.fard
fardrun test --program tests/test_branch_gate.fard
```

---

## What is next

Next repo layer:

```text
src/orgntr_prim/omir.fard
src/orgntr_prim/lower_ocir_to_omir.fard
src/orgntr_prim/x86_64_encode.fard
src/orgntr_prim/macho.fard
```

Next milestone:

```text
FARD emits the same branch-gate object structure Rust currently emits.
```

First acceptance test:

```bash
cc -arch x86_64 -o run host.c out.o target/x86_64-apple-darwin/debug/liborgntr_rt.a
./run
otool -l out.o | rg "LC_BUILD_VERSION"
```

Expected:

```text
2
cmd LC_BUILD_VERSION
```

The proof carried forward is:

```text
wrote out.o
2
cmd LC_BUILD_VERSION
```
