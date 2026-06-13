# FARD Prim

A verifiable compilation substrate that takes FARD, Python, and JavaScript source
to native x86-64 and ARM64 binaries — written entirely in FARD.

FARD is the proving ground. FARD Prim is the pitch: a compiler that targets
correctness first, then performance, portability, and eventually becomes a
verified native backend for major programming languages.

## What compiles

Any of these inputs:

   FARD:       fn add(a,b) { a + b }  add(10,32)
   Python:     def add(a, b): return a + b  (via py_to_json.py + Python ast)
   JavaScript: function add(a, b) { return a + b; }  (via Acorn)

All produce the same native binary. Same IR, same backend, same output.

## Results

   add(10,32)    = 42   arithmetic
   max(10,42)    = 42   if/else
   fact(5)       = 120  recursion
   fib(10)       = 55   double recursion
   xs[0]         = 10   list indexing
   r.a           = 42   record field access
   s[0]          = 104  string char
   adder(10)(32) = 42   closure with captured variable

## Targets

| Platform     | Format | Result |
|--------------|--------|--------|
| macOS x86-64 | Mach-O | 10/10  |
| Linux x86-64 | ELF64  | 10/10  |
| Linux ARM64  | ELF64  | 5/5    |
| macOS ARM64  | Mach-O | blocked by AppleSystemPolicy (macOS 15) |

Linux targets tested via Docker on Ubuntu 22.04.

## Pipeline

   FARD / Python / JS source
     -> frontend (language-specific AST -> UVIR)
     -> UVIR (SSA with phi nodes, type verifier)
     -> OCIR (phi elimination, register/stack abstraction)
     -> SSA opts (copy prop, const fold, DCE)
     -> OMIR (machine instruction selection)
     -> TCO (self-tail-calls -> Jmp to entry)
     -> register allocation (linear-scan; callee-saved r12-r15
        for values live across CallReloc, push/pop in prologue/epilogue)
     -> peephole (cross-block-safe copy propagation, dead-store elimination)
     -> encode + fixups (branch patching, reloc resolution)
     -> ELF64 or Mach-O binary

No external linker. No C runtime. No libSystem.

## IR layers

   UVIR   language-neutral SSA, explicit phi nodes, type verifier
   OCIR   operation-centric, register/stack abstraction
   OMIR   machine-oriented, x86-64 and ARM64 instruction selection

## Runtime

   entry stub + fard_alloc (bump allocator) + functions
   Heap: [fn_ptr, cap0, cap1, ...] for closures
   Closure ABI: closure ptr as arg0, captures via indexed heap load

## Regression

   fardrun run --program programs/regression.fard --out /tmp/reg
   python3 programs/regression_run.py /tmp/reg/result.json

10 cases, all PASS across all targets.

## Performance

   fib(35), macOS x86-64, user time:

   FARD Prim   0.085s
   gcc -O0     0.052s   (1.6x)
   gcc -O2     0.030s   (2.8x)

Achieved via:
  - Linear-scan register allocation (callee-saved r12-r15 for values
    live across recursive calls)
  - Cross-block-safe peephole (copy propagation + dead-store elimination)
  - Constant-fold isel pass: MovImm64(C)+SubI64 -> SubRegImm ->
    lea rdi,[r13-1] (9 instructions -> 1) for argument preparation

## Source

7,611 lines of FARD across 34 files in src/orgntr_prim/.

   x86_64_encode.fard    x86-64 instruction encoding, incl. register
                         operand forms for the allocator (639 lines)
   arm64_encode.fard     ARM64 instruction encoding (575 lines)
   elf_arm64.fard        ELF64 AArch64 emitter
   elf_exe.fard          ELF64 x86-64 emitter
   macho_exe.fard        Mach-O x86-64 emitter
   hir_to_uvir.fard      HIR to UVIR with phi nodes
   uvir_to_ocir.fard     phi elimination, OCIR emission
   ocir_opt.fard         copy prop, const fold, DCE
   omir_tco.fard         self-tail-call -> Jmp elimination
   omir_regalloc.fard    linear-scan register allocator (260 lines)
   omir_peephole.fard    copy propagation + DSE (283 lines)
   python_to_uvir.fard   Python subset frontend
   js_to_uvir.fard       JavaScript subset frontend

## Next

   growable heap (mmap) -> done for all ELF targets
   tail call optimization (TCO) -> done: self-tail-calls -> Jmp to entry
   register allocation -> done: linear-scan, callee-saved r12-r15
   peephole (copy prop + DSE) -> done
   list.len / list.get native -> done
   stdlib native (list.map, str.concat, rec.get)
   fardlex + fardparse + fard_eval compile natively
   delete Rust eval loop

## Repos

   https://github.com/mauludsadiq/FARD-Prim   (this repo, backend)
   https://github.com/mauludsadiq/FARD         (v0.5 compiler, written in Rust)
