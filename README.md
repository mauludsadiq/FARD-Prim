# FARD Prim

FARD is a deterministic, content-addressed language where every execution
produces a SHA-256 receipt committing to source, imports, inputs, and result.

FARD Prim is the x86-64 native backend — written entirely in FARD. It takes
the compiler from producing verified receipts to producing native machine code.

## What it does

Takes FARD source → native MH_EXECUTE binary. No linker. No C driver.
No libSystem. No dyld. Pure FARD end to end.

    FARD source
      -> fardlex (tokenize)
      -> fardparse (AST)
      -> fard_lower (IR)
      -> fard_ir_to_ocir (bridge to OCIR)
      -> verify (OCIR type check)
      -> lower_ocir_to_omir (OMIR)
      -> x86_64_encode + fixups (bytes)
      -> x86_64_link (reloc resolution)
      -> macho_exe (MH_EXECUTE)
      -> binary

## Verified native execution (Stage 8 complete)

    add(10,32)    = 42   arithmetic
    max(10,42)    = 42   if/else, CmpI64, BrCond
    fact(5)       = 120  recursion, MulI64, SubI64
    fib(10)       = 55   double recursion
    xs[0]         = 10   list indexing (make_list + get_index)
    xs[2]         = 30   list indexing offset
    r.a           = 42   record field access (make_rec + get_field)
    r.b           = 7    record second field
    s[0]          = 104  string char 'h' from "hello"
    s[4]          = 111  string char 'o' from "hello"
    adder(10)(32) = 42   closure with captured variable (x+y)

## IR ops supported

    const (int, bool, str), load, add, sub, mul
    gt, lt, le, ge, eq, ne  (CmpI64)
    branch/jump/patch_branch/patch_jump  (flat IR -> block splitting)
    call (direct), call fn_r (CallIndirect via closure ptr)
    make_list, make_rec, make_str  -> AllocHeap + StoreHeap
    get_index  -> LoadHeapDyn (ptr + 8 + idx*8)
    get_field  -> LoadHeapStaticIdx (compile-time field order map)
    make_closure  -> AllocHeap + StoreFnPtr (AbsReloc)
    global_load   -> aliased to global_store src (same name)

## Runtime

    __TEXT  entry stub (24 bytes) + fard_alloc stub (34 bytes) + functions
    __DATA  4KB bump allocator heap at 0x100002000
    Closure heap: [fn_ptr, cap0, cap1, ...]
    Closure ABI: __env__ passed as arg0, captures loaded via get_index

## Closure capture ABI

    adder(x) returns closure ptr = [fn_ptr_of_anon_, x_value]
    CallIndirect: passes closure ptr as rdi, explicit args follow
    anon_(__env__, y): loads x = get_index(__env__, 0), computes x+y

## MH_EXECUTE structure

    __PAGEZERO   vmaddr=0 vmsize=4GB
    __TEXT       vmaddr=0x100001000
    __DATA       vmaddr=0x100002000 (heap)
    __LINKEDIT

Entry stub (24 bytes):

    push rbp / mov rbp,rsp / call fard_main / mov rdi,rax
    mov rax,0x2000001 / syscall

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

## Roadmap

    Stage 8  [done]  full language native: int, bool, list, record, string, closure
    Stage 9  [next]  stdlib native (list.map, str.concat, rec.get, ...)
                     import flattening → fardlex + fardparse + fard_eval compile natively
                     delete Rust eval loop
    Stage 10         FARD ISA Phase 4 — Verilog / FPGA

## Status

- FARD v0.5.0, fardrun v1.7.1, target x86_64-apple-darwin
- Repos: https://github.com/mauludsadiq/FARD-Prim (backend)
         https://github.com/mauludsadiq/FARD (v0.5 compiler)
