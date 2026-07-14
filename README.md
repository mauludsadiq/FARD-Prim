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
   str_concat("hello"," world")            = "hello world"  string concat
   str_len("hello world")                 = 11   string length
   int_to_str(42)                          = "42"  integer to string
   str_eq(s,s)                             = 1    string equality
   adder(10)(32)                           = 42   closure with captured variable
   while 0 fn(s){s<n} fn(s){s+1} / n=10  = 10   while loop

## Targets

| Platform     | Format | Result |
|--------------|--------|--------|
| macOS x86-64 | Mach-O | 11/11 + string stdlib |
| Linux x86-64 | ELF64  | 11/11  |
| Linux ARM64  | ELF64  | 6/6    |
| macOS ARM64  | Mach-O | structurally correct; blocked by ASP on macOS 15 without provisioning profile |
| Windows x64  | PE32+  | verified structure; run on Wine/Windows  |

Linux targets tested via Docker on Ubuntu 22.04.

## Pipeline

   FARD / Python / JS source
     -> frontend (language-specific AST -> UVIR)
     -> UVIR (SSA with phi nodes, type verifier)
     -> LICM (loop invariant code motion, AST level, nested loops)
     -> loop unrolling (constant-bound while loops, up to 16 iterations)
     -> strength reduction (MulI64 by power-of-2 -> AddI64 doubling chain)

Instrumented pipeline (fard_source_to_native_pgo.fard):
     same as above, plus IncrCounter at each block entry
     entry stub: mmap profile page, dump 4096 bytes to fd=2 on exit
     profile format: 512 x 64-bit counters at profile_base + id*8
     -> OCIR (phi elimination, register/stack abstraction)
     -> SCCP (sparse conditional constant propagation)
     -> inliner (multi-block CFG inlining, threshold 12 instructions)
     -> GVN (global value numbering)
     -> MemorySSA (MemDef/MemUse/MemPhi, intra+cross-block load elimination)
     -> alias analysis (alloc-based must_not_alias, alias-aware load elim)
     -> SSA opts (copy prop, const fold, DCE, empty block elimination)
     -> dead function elimination (post-inline)
     -> loop IR (natural loop detection, IV analysis, loop SR)
     -> shared analysis (dominance, liveness, def/use, CFG, loop detection)
     -> VMIR (instruction selection, virtual registers)
     -> pre-RA scheduling (list scheduling, latency hiding)
     -> OMIR (register allocation, physical slots)
     -> interference graph RA (Chaitin-Briggs graph coloring)
     -> TCO (self-tail-calls -> Jmp to entry)
     -> register allocation (linear scan + copy coalescing;
        callee-saved r12-r15 for values live across calls)
     -> peephole (copy prop, DSE, self-move elimination,
        JccFlags+Jmp fusion, const-fold isel)
     -> encode + fixups (branch patching, reloc resolution)
     -> ELF64 or Mach-O binary

No external linker. No C runtime. No libSystem.
Heap: 4MB mmap at startup. Conservative mark-sweep GC. Bounds-checked bump allocator.

## IR layers

   UVIR   language-neutral SSA, explicit phi nodes, type verifier
   OCIR   operation-centric, register/stack abstraction
   VMIR   virtual-register machine IR (instruction selection, no allocation)
   OMIR   machine-oriented, physical registers and stack slots

## Runtime

   entry stub + fard_alloc (bump allocator) + functions
   Heap: [fn_ptr, cap0, cap1, ...] for closures
   Closure ABI: closure ptr always arg0 (__env__), actual params from arg1

## Regression

   fardrun run --program programs/regression.fard --out /tmp/reg
   python3 programs/regression_run.py /tmp/reg/result.json

11 cases, all PASS.

## Fuzzer

   python3 programs/fuzzer_v2.py 1000 42

Property-based fuzzer with 7 generators: arithmetic, recursive functions,
closures with captures, closures with conditionals, while loops,
multi-function programs, GVN stress (repeated subexpressions).
Compiles programs natively, runs them, compares exit code against
fard_eval interpreter. Bugs found so far:

  1. REX.B missing for r8-r15 in MulI64/CmpI64 reg-reg encodings.
     imul/cmp against r13 silently used rbp (same low-3-bits, no REX.B).
     Found by: recursive generator.

  2. SCCP parameter lattice initialized to Top instead of Bottom.
     meet(Const, Top)=Const incorrectly folded merge registers when
     one branch carried a parameter value and the other a constant.
     Found by: arith generator.

  3. free_vars_expr used node.then_ instead of node.then_n for if nodes.
     Crashed when if expressions appeared inside closure bodies.
     Found by: closure_cond generator.

  4. SubRegImm/CmpRegImm missing from use_slots_for_cross in peephole.
     Cross-block CopyI64 feeding a SubRegImm was incorrectly eliminated,
     leaving the destination slot unwritten (stale stack value at runtime).
     Found by: multi_fn generator.

  5. StoreFnPtr/MakeClosure ptr_slot not marked unrewritable in RA.
     RA coalesced heap pointer slot to r12; StoreFnPtr then read stale
     stack slot -> crash. Found by: multi_fn generator (post-VMIR split).

500 cases: 460 pass, 40 skip, 0 fail (all 7 generators).

## Performance

   fib(35), macOS x86-64, user time:

   FARD Prim   0.087s
   gcc -O0     0.056s   (1.6x slower than gcc -O0)
   gcc -O2     0.033s   (2.6x slower than gcc -O2)

Achieved via:
  - LICM: loop invariant code motion at AST level (arithmetic + field access)
  - SCCP: sparse conditional constant propagation
  - Multi-block inliner: full CFG inlining <= 12 instructions
  - Dead function elimination: removes inlined-away functions post-inline
  - GVN: eliminates redundant computations (n*n+n*n -> 1x mul + add)
  - Pre-RA scheduling: list scheduling on VMIR hides load/mul latency
    (xs[0]+xs[1]: both loads now issue back-to-back, overlapping latency)
  - Empty block elimination: collapses chains of unconditional jumps
  - Copy coalescing: merge-register assignment, eliminates MovRegToReg
  - Self-move elimination: removes MovRegToReg(r, r) no-ops
  - JccFlags+Jmp fusion: eliminates double-branch in if/else hot paths
  - Const-fold isel: MovImm64+Sub/AddI64 -> lea; MovImm64+CmpI64 -> cmp
  - CmpRegImmFlags+JccFlags: setle/movzx/store/test -> cmp+jcc
  - Interference graph RA: Chaitin-Briggs coloring, copy coalescing,
    precise live range interference with inclusive bounds,
    loop-depth spill cost weighting (10x per loop level)
  - Loop unrolling: constant-bound while loops fully unrolled at AST level;
    SCCP+const-fold collapse to single constant (zero overhead)
  - Strength reduction: MulI64(n, 2^k) -> k AddI64 doublings (n*4 = 2 adds);
    extended to non-power-of-2: n*3=2adds, n*5=3adds, n*6=3adds, n*7=4adds
  - PGO Phase 1: instrumented compilation, static __profile section in __DATA,
    IncrCounter at each block, profile dump to fd=2 on exit
  - PGO Phase 2: profile-guided inliner; hot functions (count>50) get
    threshold 50, cold (count=0) never inlined; pgo_compile.py driver
  - ARM64 Mach-O: complete emitter with all 16 load commands required by
    Apple Silicon (LC_DYLD_CHAINED_FIXUPS, LC_LOAD_DYLIB libSystem, etc.)
    Binary validates via codesign --verify; blocked by AMFI/SIP ad-hoc signing
  - PGO Phase 3A: profile-guided block reordering; greedy trace scheduling
    puts hottest successor as fallthrough, return blocks always last
  - PGO Phase 3B: hot function ordering; hottest functions emitted first
    in __text segment for I-cache locality; entry always last
  - PGO Phase 3C: profile-guided RA spill cost weighting; blocks weighted
    by execution count, cheapest slots chosen as spill candidates
  - Python frontend: end-to-end Python->native via compile_python.py
    add/fact/fib verified correct; fixes: EpilogueRet for multi-return
    functions, DFE entry root, If early-return, Expr ret_reg tracking
  - JavaScript frontend: end-to-end JS->native via compile_js.py + Acorn
    same fixes applied; add/fact/fib verified correct
  - DWARF4 debug symbols: __DWARF segment with __debug_abbrev,
    __debug_info, __debug_str; DW_TAG_compile_unit + DW_TAG_subprogram
    per function with correct vmaddr ranges; verified with dwarfdump
  - MemorySSA Phase 1: memory version tracking (MemDef/MemUse/MemBarrier);
    redundant load elimination; r.a+r.a -> 1 load (was 2)
  - MemorySSA Phase 2: dominance frontier computation (Cooper et al.)
    + MemPhi insertion via iterated dominance frontier (Cytron et al.);
    ocir_domtree.fard: RPO, idom tree, dominance frontiers
  - MemorySSA Phase 3: version renaming via DFS over dominator tree;
    MemPhi incoming slots filled with correct live-out versions;
    build_full_memssa: complete 3-phase pipeline in one call
  - LICM extended to record field accesses (t=get): r.a hoisted out
    of while loop body; LoadHeapStaticIdx moves from closure to caller
  - Interprocedural alias analysis: alloc-based origin tracking;
    must_not_alias when ptrs trace to different AllocHeap instructions;
    alias-aware load elimination preserves cache across non-aliasing stores
  - Cross-block redundant load elimination: domtree-walk GVN with
    MemorySSA versions; available load table flows dom->dominated;
    r.a+r.a across blocks -> 1 load + copy
  - __debug_line: DWARF4 line number table; DW_LNE_set_address per
    function, DW_LNS_copy rows, DW_LNE_end_sequence; 111 bytes;
    verified with dwarfdump; sidecar .dwarf file due to macOS
    __LINKEDIT-must-be-last constraint on embedded DWARF
  - Structured loop IR: natural loop detection via back edges + idom;
    loop body/header/latch/preheader/exits; IV analysis via step closure;
    while 0 fn(s){s<n} fn(s){s+1} -> {init=0, step=1, op=AddI64}
  - Loop strength reduction: non-power-of-2 multipliers -> addition chains;
    add_chain_for handles {3,5,6,7,9,10,12,15}; s*3 -> 2 adds;
    verified: MulI64 eliminated from step closure
  - Dead store elimination: intra-block DSE via alloc-origin tracking;
    StoreHeap never-read -> eliminated; {a:n, b:n+1} reading only .a
    eliminates 2 of 3 stores (fn_ptr@0 and b@16); 11/11 regression PASS
  - PE/COFF target: Windows x86-64 PE32+ executable emitter;
    pe_exe.fard: DOS stub, COFF header, PE32+ optional header,
    .text + .idata sections, ExitProcess import from kernel32.dll;
    entry stub: call fard_main, mov rcx rax, call ExitProcess via IAT;
    1536 bytes; verified MZ/PE/ImageBase/EntryPoint/sections
  - Standard library: print(str) and print_int(n) as 285-byte x86-64 stubs;
    write syscall direct, no libc; FARD ABI-aware (rsi=first arg);
    neg op fixed (was inst_add instead of SubI64); print/print_int verified
  - GC Phase 1+2: 4MB mmap heap, conservative mark-sweep GC;
    GC header (ptr-8) stores size+mark bit; loop(300000) allocating
    32-byte records -> GC fires, collects, returns 42 ✓
  - ARM64 parity: full VMIR pipeline, callee-saved reg handling,
    large literal encoding via bits.bshl (FARD truncates >2^31)

## Source

16,219 lines of FARD across 69 files in src/orgntr_prim/.

   x86_64_encode.fard      x86-64 instruction encoding (775 lines)
   fard_ir_to_ocir.fard    flat IR to OCIR block structure (586 lines)
   fard_lower.fard         AST to flat IR, closures, while loops, print (589 lines)
   fardparse.fard          FARD parser with while expression (520 lines)
   macho_exe.fard          Mach-O x86-64 emitter (343 lines)
   omir_peephole.fard      copy prop + DSE + fusion + const fold (521 lines)
   arm64_encode.fard       ARM64 instruction encoding (575 lines)
   omir_regalloc.fard      linear scan + copy coalescing (358 lines)
   ocir_inline.fard        multi-block CFG inliner (216 lines)
   ocir_sccp.fard          sparse conditional constant propagation (210 lines)
   ocir_opt.fard           copy prop, const fold, DCE, empty block elim (306 lines)
   ocir_gvn.fard           global value numbering (110 lines)
   ocir_gvn_mem.fard       cross-block GVN via MemorySSA (160 lines)
   ocir_to_vmir.fard       OCIR -> VMIR instruction selection (124 lines)
   vmir_sched.fard         pre-RA list scheduling, latency hiding (229 lines)
   vmir_to_omir.fard       VMIR -> OMIR register allocation (237 lines)
   ocir_memssa.fard        MemorySSA: MemDef/MemUse/MemPhi + renaming (571 lines)
   ocir_domtree.fard       RPO, idom, dominance frontiers (191 lines)
   ocir_alias.fard         alloc-based alias analysis (173 lines)
   ocir_loop_ir.fard       structured loop IR + IV analysis (250 lines)
   macho_dwarf.fard        DWARF4 debug info emitter (290 lines)
   ast_licm.fard           loop invariant code motion, AST level (216 lines)
   ocir_dfe.fard           dead function elimination post-inline (53 lines)
   ocir_dse.fard           dead store elimination, intra-block (188 lines)
   pe_exe.fard             PE32+ Windows x86-64 emitter (285 lines)
   fard_source_to_pe.fard  FARD -> Windows PE pipeline (55 lines)
   fard_source_to_native_arm64.fard ARM64 ELF64 pipeline (47 lines)
   ast_unroll.fard         loop unrolling, constant-bound while (193 lines)
   ocir_sr.fard            strength reduction, mul->add + small-k chains (195 lines)
   fard_gc.fard            GC entry stub, mark-sweep infrastructure (94 lines)
   lower_ocir_to_omir.fard OCIR -> OMIR (ARM64/ELF legacy path) (391 lines)
   python_to_uvir.fard     Python subset frontend (289 lines)
   js_to_uvir.fard         JavaScript subset frontend (270 lines)

## Next

   Standard library: string ops, file I/O (print/print_int done)
   Cross-block DSE (extend to multi-block functions)
   Type tags for GC precision (conservative currently safe)
   Wine/Windows validation of PE exit code

## Repos

   https://github.com/mauludsadiq/FARD-Prim   (this repo, backend)
   https://github.com/mauludsadiq/FARD         (v0.5 compiler, written in Rust)
