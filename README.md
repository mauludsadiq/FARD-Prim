# FARD Prim

FARD is a deterministic, content-addressed language where every execution
produces a SHA-256 receipt committing to source, imports, inputs, and result.
Two runs of the same program on the same inputs produce the same digest on any
machine at any time.

FARD Prim is the x86-64 native backend — written entirely in FARD. It takes
the compiler from producing verified receipts to producing native machine code.
2,663 lines of pure FARD across 24 files.

## Verified results

   add2(40, 2) -> exit: 42
   fard_main() -> exit: 2   (branch gate, conditional branch)

Two FARD functions compiled from OCIR through OMIR to x86-64, linked by ld,
executing natively. No C driver. No libclang_rt. Two Mach-O objects emitted
entirely in FARD, linked against libSystem only.

## Pipeline

Six stages, all in FARD:

   Stage 1: lower_ocir_to_omir  — slot assignment, frame sizing, param moves,
                                   branch lowering, CallI64 lowering (225 lines)
   Stage 2: x86_64_encode       — instruction encoding, SysV AMD64 ABI,
                                   arg register loads/stores (263 lines)
   Stage 3: x86_64_fixups       — label scanning, forward branch patching (123 lines)
   Stage 4: x86_64_link         — symbol table, call reloc resolution (99 lines)
   Stage 5: macho_emit          — Mach-O x86_64 MH_OBJECT emitter + entry stub (544 lines)

Two objects produced per program:

   program.o     — compiled FARD functions: OCIR -> OMIR -> encode -> fixup -> link -> Mach-O
   fard_entry.o  — entry stub: _main calls _fard_main, passes result to _exit

Linked with:

   ld -lSystem fard_entry.o program.o

## IR

### OCIR (typed source IR)

   func_with_params(name, params, blocks)
   param(reg, ty)                          -- {reg: int, ty: "I64"|"Bool"|"FardVal"}
   inst_imm_i64(dst, val)
   inst_imm_bool(dst, val)
   inst_add_i64(dst, lhs, rhs)
   inst_call_i64(dst, callee, args)        -- internal function call
   inst_box_int(dst, src)
   inst_call_add_boxed(dst, lhs, rhs)      -- external runtime call
   inst_call_mul_boxed(dst, lhs, rhs)
   term_ret_i64(src)
   term_br(to)
   term_br_cond(cond, then_blk, else_blk)

### OMIR (machine IR)

   prologue(frame_size)     epilogue(frame_size)
   mov_imm64                mov_stack_to_reg       mov_reg_to_stack
   add_reg_stack            cmp_stack_zero
   store_param(arg_idx, slot)   -- mov [rbp+slot], arg_reg_n  (function entry)
   load_arg(arg_idx, slot)      -- mov arg_reg_n, [rbp+slot]  (call setup)
   jne(label)   jmp(label)   bind_label(label)
   call_reloc(name)
   lea_rdi_rbp   mov_rsi_rbp   mov_rdx_rbp   mov_rcx_rbp   mov_r8_rbp
   ret_i64

## Calling Convention

Internal calls (SysV AMD64):

   arg 0 -> rdi   arg 1 -> rsi   arg 2 -> rdx
   arg 3 -> rcx   arg 4 -> r8    arg 5 -> r9
   return value in rax

External runtime calls:

   fard_add_boxed_out(out: *mut FardVal, a: FardVal, b: FardVal)
   rdi=&dst  rsi=lhs.tag  rdx=lhs.payload  rcx=rhs.tag  r8=rhs.payload

## Tests

89 tests across 9 suites, all passing.

   fardrun test --program tests/test_lower_ocir_to_omir.fard   # 5
   fardrun test --program tests/test_x86_64_encode.fard        # 12
   fardrun test --program tests/test_x86_64_fixups.fard        # 5
   fardrun test --program tests/test_x86_64_link.fard          # 7
   fardrun test --program tests/test_asc7_profile.fard         # 10
   fardrun test --program tests/test_x86_64_cc.fard            # 9
   fardrun test --program tests/test_macho_emit.fard           # 20
   fardrun test --program tests/test_macho_entry.fard          # 7
   fardrun test --program tests/test_ocir_calls.fard           # 9

## Source

   src/orgntr_prim/
     ocir.fard               typed IR (51 lines)
     omir.fard               machine IR (139 lines)
     lower_ocir_to_omir.fard stage 1 lowering (225 lines)
     x86_64_encode.fard      stage 2 encoding (263 lines)
     x86_64_fixups.fard      stage 3 branch fixups (123 lines)
     x86_64_link.fard        stage 4 linker (99 lines)
     macho_emit.fard         stage 5 Mach-O emitter + entry stub (544 lines)
     asc7_profile.fard       ASC7 code_safe collapse kernel (206 lines)
     verify.fard             OCIR type verifier (104 lines)
     run_gate.fard           branch gate driver + trust record (55 lines)
     hash.fard               trust record construction (20 lines)
     target.fard             target triple (18 lines)

## Run

   fardrun run --program programs/branch_gate.fard --out out/branch_gate
   cat out/branch_gate/result.json

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

asc7_graph_hash commits to the DSU collapse kernel — 95 printable ASCII chars,
three glyph classes ({0,O,o}, {1,l,I,|}, {',`}), syntax_strict, 89-char
witness alphabet.

## Mach-O Output

   LC_SEGMENT_64     __TEXT,__text
   LC_BUILD_VERSION  platform=MACOS minos=11.0
   LC_SYMTAB         nlist_64, underscore-prefixed, correct defined/undef counts
   LC_DYSYMTAB       correct iextdefsym/nextdefsym/iundefsym/nundefsym

Relocs emitted as X86_64_RELOC_BRANCH (pcrel=1, len=4, type=2) with addr
pointing to the rel32 operand field (opcode+1).

## Status

- FARD v0.5.0, fardrun v1.7.1, target x86_64-apple-darwin
- ld used for final link — MH_EXECUTE emission not yet implemented
- Boxed arithmetic path (fard_add_boxed_out) lowered and encoded,
 pending native proof with liborgntr_rt.a

## Roadmap

   done   function arguments (SysV AMD64 param/arg moves)
   done   internal FARD-to-FARD calls with resolved relocs
   done   return value ABI (rax)
   next   boxed arithmetic — add2_boxed(40, 2) -> exit: 42 via runtime
   then   MH_EXECUTE direct emission

## Context

FARD is in Stage 8 of self-hosting: 15 stdlib modules in pure FARD,
fard_eval.fard running as a pure FARD evaluator. Stage 7 complete: native
linker resolves cross-module calls with no Rust at runtime.

FARD Prim is the bridge from that pipeline to the language compiling itself
to native x86-64 and executing correctly.

   https://github.com/mauludsadiq/FARD
