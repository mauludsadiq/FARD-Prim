# FARD Prim

A verifiable compilation substrate — written entirely in FARD.

FARD is the proving ground. FARD Prim is the pitch: a compiler that targets
correctness first, then performance, portability, and eventually becomes the
verified native backend for major programming languages.

## Status

Stage 8 complete. All core FARD constructs compile to native x86-64 MH_EXECUTE.

    add(10,32)    = 42   arithmetic
    max(10,42)    = 42   if/else
    fact(5)       = 120  recursion
    fib(10)       = 55   double recursion
    xs[0]         = 10   list indexing
    r.a           = 42   record field access
    s[0]          = 104  string char access
    adder(10)(32) = 42   closure with captured variable

## Pipeline

    FARD source
      -> fardlex (tokenize)
      -> fardparse (AST)
      -> fard_lower (IR)
      -> fard_ir_to_ocir (bridge to OCIR)
      -> verify (OCIR type check)
      -> lower_ocir_to_omir (OMIR)
      -> x86_64_encode + fixups
      -> x86_64_link (reloc resolution)
      -> macho_exe (MH_EXECUTE)
      -> binary

No linker. No C driver. No libSystem. No dyld.

## IR ops supported

    const (int, bool, str), load, add, sub, mul
    gt, lt, le, ge, eq, ne  (CmpI64)
    branch/jump/patch_branch/patch_jump
    call (direct), call fn_r (CallIndirect)
    make_list, make_rec, make_str  -> heap allocation
    get_index  -> LoadHeapDyn
    get_field  -> LoadHeapStaticIdx
    make_closure  -> AllocHeap + StoreFnPtr (AbsReloc)
    global_load   -> aliased to global_store src

## Runtime

    __TEXT  entry stub (24 bytes) + fard_alloc (34 bytes) + functions
    __DATA  4KB bump allocator heap at 0x100002000
    Closure heap: [fn_ptr, cap0, cap1, ...]
    Closure ABI: closure ptr as arg0, captures via get_index(__env__, i)

## Regression suite

   fardrun run --program programs/regression.fard --out /tmp/reg
   python3 programs/regression_run.py /tmp/reg/result.json

10 cases, all PASS:
   add(10,32)=42    max(10,42)=42    fact(5)=120      fib(10)=55
   xs[0]=10         xs[2]=30         r.a=42           r.b=7
   adder(10)(32)=42 (closure+capture)   s[0]=104 (string)

## Roadmap

### Correctness track
    [done]  Phase 1 — Semantic correctness
            add/max/fact/fib/list/record/string/closure all match fardrun
    [done]  Phase 2 — Verifier completion
            UNDEF_REG: undefined register rejected at use site
            RET_I64 src verified defined on all paths
            CALL_ARITY_MISMATCH: arg count vs callee arity
            call arg registers verified defined
            BrCond cond defined + both branch targets exist
            Br target label exists
            duplicate function name rejected
            entry function present
            CFG join dominance: dataflow intersection at join points
            reg defined on only one branch rejected at join
    [done]  Phase 3 — Regression matrix
            one command: fardrun run --program programs/regression.fard
            runner: python3 programs/regression_run.py /tmp/reg/result.json
            10 cases: add, max, fact, fib, list, rec, string, closure

### IR track
    [done]  Phase 4 — HIR pipeline complete
            AST -> HIR -> OCIR -> verify -> OMIR -> x86-64 -> MH_EXECUTE
            hir.fard: structured HIR (if/else, let, fn, call, list, rec)
            ast_to_hir.fard: full AST -> HIR lowering
            hir_to_ocir.fard: single recursive lower_hir_expr (284 lines)
              closures with captures, get_field, let-chain, list, rec
              free_vars analysis, global field_order pre-pass
            Verified: add=42, fact=120, get_field=42, let_chain=42, closure=42
    [done]  UVIR — Universal Verified IR
            uvir.fard: types, values, instructions, phi, pretty-printer
            hir_to_uvir.fard: FARD HIR -> UVIR with explicit phi nodes
            uvir_to_ocir.fard: phi elimination via predecessor copies
            Verified: add=42, max=42, fact=120, fib=55, closure=42
            Example: fn max -> phi([%0 from then], [%1 from else])
    [done]  UVIR verifier — type-check UVIR before lowering to OCIR
            UNDEF_REG, INT_ARITH_TYPE, CALL_ARITY_MISMATCH, BRCOND_COND_TYPE
            BR_TARGET_MISSING, DUPLICATE_FUNC, phi defines dst as Int
            dataflow env propagation + predecessor intersection
    [done]  Python subset frontend -> UVIR -> native x86-64
            python_to_uvir.fard: Python JSON AST -> UVIR
            bridge: py_to_json.py (Python stdlib ast -> JSON)
            fact(5)=120, fib(10)=55, max(10,42)=42 from Python source
            macho_exe: entry_func now parameterized (not hardcoded fard_main)
    [done]  SSA optimization passes: copy prop, const fold, DCE
            ocir_opt.fard (211 lines): within-block copy elimination, const folding
            fact(5): 11 -> 10 instructions. Regression: 10/10 PASS
    [done]  ELF64 backend: Linux x86-64 native executables
           elf_exe.fard: ELF header, PT_LOAD segments, Linux syscall stub
           link_module_with_vmaddr: parameterized linker for non-Mach-O
           Linux regression 10/10: add, max, fact, fib, list[0], list[2],
             rec.a, rec.b, closure, str_char — full parity with macOS on Ubuntu 22.04 via Docker
           str_char fixed: str.char_code() for integer code point
    [done]  ARM64 backend: ELF Linux ARM64 (Docker --platform linux/arm64)
            add=42, max=42, fact=120, fib=55 via Docker ubuntu:22.04
            macOS ARM64: blocked by AppleSystemPolicy on macOS 15
   [next]  stdlib native -> fard_eval native -> delete Rust eval loop
    [done]  JavaScript subset frontend -> UVIR -> native x86-64
            js_to_uvir.fard: Acorn AST JSON -> UVIR
            bridge: js_to_json.js (Acorn parser)
            fact(5)=120, fib(10)=55, max(10,42)=42 from JS source
            early-return fix: then-branch with return gets RetI64 directly
    [next]  UVIR — Universal Verified IR
            language-neutral: functions, closures, heap objects, effects,
            direct/indirect calls, phi/join values, module boundaries

### Optimization track (after correctness locked)
    [ ]     SSA — explicit phi nodes + dominance
    [ ]     copy propagation + dead code elimination (first safe passes)
    [ ]     constant folding / propagation
    [ ]     closure inlining
    [ ]     register allocation

### Backend track
    [done]  ELF (Linux)
    [ ]     ARM64 (Apple Silicon, Linux)
    [ ]     WASM
    [ ]     DWARF debug info
    [ ]     Dynamic libraries

### Self-hosting track
    [next]  stdlib native (list.map, str.concat, rec.get, ...)
    [ ]     import flattening -> fardlex + fardparse + fard_eval compile natively
    [ ]     delete Rust eval loop
    [ ]     FARD compiles FARD Prim compiles FARD

### Language frontend track (after UVIR/SSA stable)
    [ ]     Python subset (stress-tests dynamic objects, closures, dicts)
    [ ]     JavaScript/TypeScript subset
    [ ]     Rust MIR-style path
    [ ]     C, Go, Swift, Java

## Architecture principle

    FARD source   -> FARD frontend   \
    Python source -> Python frontend  \
    JS source     -> JS frontend       -> UVIR -> SSA -> OMIR -> Native/WASM
    Rust source   -> Rust frontend    /

Every language keeps its surface semantics.
Every compilation lowers into a verified common substrate.
Every transformation emits receipts.

## Source

    src/orgntr_prim/
      fard_source_to_native.fard  end-to-end driver
      fard_ir_to_ocir.fard        v0.5 IR -> OCIR bridge
      verify.fard                 OCIR type verifier
      lower_ocir_to_omir.fard     OMIR lowering
      x86_64_encode.fard          instruction encoding
      x86_64_fixups.fard          branch patching
      x86_64_link.fard            symbol table + reloc resolution
      macho_exe.fard              MH_EXECUTE emitter
      ocir.fard / omir.fard       IR definitions

## Repos

    https://github.com/mauludsadiq/FARD-Prim   (backend)
    https://github.com/mauludsadiq/FARD         (v0.5 compiler)
