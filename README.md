# FARD Prim

FARD is a deterministic, content-addressed language where every execution
produces a SHA-256 receipt committing to source, imports, inputs, and result.
Two runs of the same program on the same inputs produce the same digest on any
machine at any time.

FARD Prim is the x86-64 native backend — written entirely in FARD. It takes
the compiler from producing verified receipts to producing native machine code.
2,501 lines of pure FARD across 24 files.

No C driver. No libclang_rt. Two Mach-O objects emitted entirely in FARD,
linked by ld against libSystem only, executing natively:

    /tmp/fard_native3 ; echo "exit: $?"
    exit: 2

## Pipeline

Six stages, all in FARD:

    Stage 1: lower_ocir_to_omir  — slot assignment, frame sizing, branch lowering (188 lines)
    Stage 2: x86_64_encode       — instruction encoding, rel32 placeholders (239 lines)
    Stage 3: x86_64_fixups       — label scanning, forward branch patching (123 lines)
    Stage 4: x86_64_link         — symbol table, call reloc resolution (99 lines)
    Stage 5: macho_emit          — Mach-O x86_64 MH_OBJECT emitter + entry stub (469 lines)

Two objects produced:

    fard_main.o   — compiled branch gate: OCIR -> OMIR -> encode -> fixup -> link -> Mach-O
    fard_entry.o  — entry stub: _main calls _fard_main, passes result to _exit

Linked with:

    ld -lSystem fard_entry.o fard_main.o

## Source

    src/orgntr_prim/
      ocir.fard               typed IR definitions (41 lines)
      omir.fard               machine IR definitions (122 lines)
      lower_ocir_to_omir.fard stage 1 lowering (188 lines)
      x86_64_encode.fard      stage 2 encoding — SysV AMD64 ABI (239 lines)
      x86_64_fixups.fard      stage 3 branch fixups (123 lines)
      x86_64_link.fard        stage 4 linker (99 lines)
      macho_emit.fard         stage 5 Mach-O object emitter + entry stub (469 lines)
      asc7_profile.fard       ASC7 code_safe collapse kernel (206 lines)
      verify.fard             OCIR type verifier (104 lines)
      run_gate.fard           branch gate driver + trust record (55 lines)
      hash.fard               trust record construction (20 lines)
      target.fard             target triple (18 lines)

## Tests

75 tests across 8 suites, all passing.

    fardrun test --program tests/test_lower_ocir_to_omir.fard   # 5
    fardrun test --program tests/test_x86_64_encode.fard        # 12
    fardrun test --program tests/test_x86_64_fixups.fard        # 5
    fardrun test --program tests/test_x86_64_link.fard          # 7
    fardrun test --program tests/test_asc7_profile.fard         # 10
    fardrun test --program tests/test_x86_64_cc.fard            # 9
    fardrun test --program tests/test_macho_emit.fard           # 20
    fardrun test --program tests/test_macho_entry.fard          # 7

## Run

    fardrun run --program programs/branch_gate.fard --out out/branch_gate
    cat out/branch_gate/result.json

The result includes the encoded function, OCIR hash, and a full trust record
committing to the ASC7 code_safe graph hash, FARD version, and target triple.

## Trust Record

Every run produces a cryptographically committed trust record:

    {
      fard_version:    "0.5.0",
      asc7_graph_hash: "sha256:ee0f3eca49ca0c79d348c6d1993eb384928f6b14...",
      ocir_hash:       "sha256:5f5a22b97ab563a38f6a8e9e27eb47c34adcc178...",
      h_sem_bits:      0,
      delta:           0,
      target:          "x86_64-apple-darwin"
    }

asc7_graph_hash commits to the DSU collapse kernel used to normalize source
before parsing — 95 printable ASCII chars, three glyph classes ({0,O,o},
{1,l,I,|}, {',`}), syntax_strict role enforcement, 89-char witness alphabet.

## Calling Convention

External runtime calls follow SysV AMD64:

    fard_add_boxed_out(out: *mut FardVal, a: FardVal, b: FardVal)

    rdi = &dst (lea from stack slot)
    rsi = lhs.tag+pad  (qword [rbp + lhs_slot + 0])
    rdx = lhs.payload  (qword [rbp + lhs_slot + 8])
    rcx = rhs.tag+pad  (qword [rbp + rhs_slot + 0])
    r8  = rhs.payload  (qword [rbp + rhs_slot + 8])

## Mach-O Output

Two valid x86_64 MH_OBJECT files:

    LC_SEGMENT_64     __TEXT,__text
    LC_BUILD_VERSION  platform=MACOS minos=11.0
    LC_SYMTAB         nlist_64 entries, underscore-prefixed names
    LC_DYSYMTAB       correct iextdefsym/nextdefsym/iundefsym/nundefsym counts

Unresolved external call relocs emitted as X86_64_RELOC_BRANCH (pcrel=1,
len=4, type=2) with addr pointing to the rel32 operand field (opcode+1).

## Status

- FARD v0.5.0, fardrun v1.7.1, target x86_64-apple-darwin
- ld is still used for the final link step — direct executable emission
  (MH_EXECUTE with LC_MAIN and mapped segments) not yet implemented
- call relocs to external symbols (fard_add_boxed_out etc.) tracked and
  emitted correctly; resolution requires linking against liborgntr_rt.a

## Context

FARD is in Stage 8 of self-hosting: 15 stdlib modules in pure FARD,
fard_eval.fard running as a pure FARD evaluator. Stage 7 complete: native
linker resolves cross-module calls with no Rust at runtime.

FARD Prim is the bridge from that pipeline to the language compiling itself
to native x86-64 and executing correctly.

    https://github.com/mauludsadiq/FARD

## License

MUI
