# FARD Prim

FARD is a deterministic, content-addressed language where every execution
produces a SHA-256 receipt committing to source, imports, inputs, and result.
Two runs of the same program on the same inputs produce the same digest on any
machine at any time.

FARD Prim is the x86-64 native backend — written entirely in FARD. It takes
the compiler from producing verified receipts to producing native machine code.
1,125 lines of pure FARD across 16 files.

## What it does

Three-stage pipeline from typed IR to native bytes:

   OCIR  ->  lower_ocir_to_omir  ->  OMIR  ->  x86_64_encode  ->  x86_64_fixups  ->  native x86-64

- Stage 1: slot assignment, frame sizing, branch lowering (174 lines)
- Stage 2: instruction encoding, rel32 placeholders (200 lines)
- Stage 3: label scanning, forward branch patching, reloc tracking (123 lines)

## Run

   fardrun run --program programs/branch_gate.fard --out out/branch_gate
   cat out/branch_gate/result.json

The result includes the encoded function, verified execution proof, OCIR hash,
and trust record — all content-addressed.

## Test

   fardrun test --program tests/test_lower_ocir_to_omir.fard
   fardrun test --program tests/test_x86_64_encode.fard
   fardrun test --program tests/test_x86_64_fixups.fard

22 tests. All pass.

## Source

   src/orgntr_prim/
     ocir.fard               typed IR definitions (41 lines)
     omir.fard               machine IR definitions (97 lines)
     lower_ocir_to_omir.fard stage 1 lowering (174 lines)
     x86_64_encode.fard      stage 2 encoding (200 lines)
     x86_64_fixups.fard      stage 3 fixups (123 lines)
     verify.fard             execution verification (104 lines)
     run_gate.fard           branch gate driver (52 lines)
     hash.fard               trust record construction (20 lines)
     target.fard             target triple (18 lines)

## Context

FARD is currently in Stage 8 of self-hosting: 15 stdlib modules rewritten in
pure FARD, fard_eval.fard running as a pure FARD evaluator. The full compiler
pipeline (fardlex, fardparse, fard_lower, fard_codegen, fard_elf, fard_link)
compiles to native ELF. Stage 7 is complete: cross-module calls resolve through
the native linker with no Rust at runtime.

FARD Prim is the bridge from that pipeline to the language running itself end
to end on native x86-64.

   https://github.com/mauludsadiq/FARD


# License

MUI