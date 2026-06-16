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

  add(10,32)                              = 42   arithmetic
  max(10,42)                              = 42   if/else
  fact(5)                                 = 120  recursion
  fib(10)                                 = 55   double recursion
  xs[0]                                   = 10   list indexing
  r.a                                     = 42   record field access
  s[0]                                    = 104  string char
  adder(10)(32)                           = 42   closure with captured variable
  while 0 fn(s){s<n} fn(s){s+1} / n=10  = 10   while loop

## Targets

| Platform     | Format | Result |
|--------------|--------|--------|
| macOS x86-64 | Mach-O | 11/11  |
| Linux x86-64 | ELF64  | 11/11  |
| Linux ARM64  | ELF64  | 5/5    |
| macOS ARM64  | Mach-O | blocked by AppleSystemPolicy (macOS 15) |

Linux targets tested via Docker on Ubuntu 22.04.

## Pipeline

  FARD / Python / JS source
    -> frontend (language-specific AST -> UVIR)
    -> UVIR (SSA with phi nodes, type verifier)
    -> OCIR (phi elimination, register/stack abstraction)
    -> SCCP (sparse conditional constant propagation)
    -> inliner (multi-block CFG inlining, threshold 12 instructions)
    -> GVN (global value numbering, eliminates redundant computations)
    -> SSA opts (copy prop, const fold, DCE, empty block elimination)
    -> OMIR (machine instruction selection)
    -> TCO (self-tail-calls -> Jmp to entry)
    -> register allocation (linear-scan; callee-saved r12-r15
       for values live across calls, push/pop in prologue/epilogue)
    -> peephole (cross-block-safe copy propagation, dead-store elimination,
       CmpRegImmFlags+JccFlags fusion, const-fold isel)
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
  Closure ABI: closure ptr always as arg0 (__env__), captures via
               indexed heap load, actual params from arg1 onward

## Regression

  fardrun run --program programs/regression.fard --out /tmp/reg
  python3 programs/regression_run.py /tmp/reg/result.json

11 cases, all PASS across all targets.

## Performance

  fib(35), macOS x86-64, user time:

  FARD Prim   0.079s
  gcc -O0     0.120s   (1.5x faster)
  gcc -O2     0.030s   (2.6x slower than gcc -O2)

Achieved via:
 - SCCP: sparse conditional constant propagation, dead branch elimination
 - Multi-block inliner: full CFG inlining of functions <= 12 instructions
   across all blocks, including branches. classify(5) compiles to mov+ret.
 - GVN: eliminates redundant computations (n*n+n*n -> 1x mul + add)
 - Empty block elimination: collapses chains of unconditional jumps
 - Linear-scan register allocation (callee-saved r12-r15 for values
   live across recursive calls)
 - Const-fold isel (runs before peephole):
     MovImm64(C)+Sub/AddI64 -> SubRegImm/AddRegImm -> lea rdi,[r13-1]
     MovImm64(C)+CmpI64 -> CmpRegImm -> cmp r13,1
 - CmpRegImmFlags+JccFlags: collapses setle/movzx/store/test -> cmp+jcc
 - AddRegReg: fib(n-1)+fib(n-2) add -> 1 instruction
 - Spill-fold: MovRegToStack+MovStackToReg -> MovRegToReg

## Source

9,967 lines of FARD across 40 files in src/orgntr_prim/.

  x86_64_encode.fard    x86-64 instruction encoding (775 lines)
  fard_ir_to_ocir.fard  flat IR to OCIR block structure (586 lines)
  fard_lower.fard       AST to flat IR lowering, closures, while loops (589 lines)
  fardparse.fard        FARD parser with while expression support (520 lines)
  macho_exe.fard        Mach-O x86-64 emitter (343 lines)
  omir_peephole.fard    copy prop + DSE + const fold isel (515 lines)
  arm64_encode.fard     ARM64 instruction encoding (575 lines)
  omir_regalloc.fard    linear-scan register allocator (305 lines)
  ocir_inline.fard      multi-block CFG inliner (216 lines)
  ocir_sccp.fard        sparse conditional constant propagation (205 lines)
  ocir_opt.fard         copy prop, const fold, DCE, empty block elim (306 lines)
  ocir_gvn.fard         global value numbering (110 lines)
  lower_ocir_to_omir.fard  OCIR to OMIR instruction selection (391 lines)
  macho_emit.fard       Mach-O segment/section layout (549 lines)
  python_to_uvir.fard   Python subset frontend (289 lines)
  js_to_uvir.fard       JavaScript subset frontend (270 lines)

## Next

  interference-graph register coalescing (eliminate MovRegToReg)
  instruction scheduling (hide load latency)
  LICM (loop invariant code motion, requires while loop back-edges)
  ARM64 optimizer parity
  stdlib native (list.map, str.concat, rec.get)
  dead function elimination post-SCCP+inline
  property-based fuzzer for regression

## Repos

  https://github.com/mauludsadiq/FARD-Prim   (this repo, backend)
  https://github.com/mauludsadiq/FARD         (v0.5 compiler, written in Rust)
