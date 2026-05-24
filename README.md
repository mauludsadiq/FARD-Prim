# FARD Prim

FARD is a deterministic, content-addressed language where every execution
produces a SHA-256 receipt committing to source, imports, inputs, and result.
Two runs of the same program on the same inputs produce the same digest on any
machine at any time.

FARD Prim is the x86-64 native backend — written entirely in FARD. It takes
the compiler from producing verified receipts to producing native machine code.
3,221 lines of pure FARD across 25 files.

## ld is gone

FARD Prim now emits a complete Mach-O executable directly. No linker. No C
driver. No libSystem. No dyld.

    OCIR -> lower -> OMIR -> encode -> fixup -> link -> MH_EXECUTE -> exit: 2

The executable is emitted as bytes, written to disk, chmod 755, and run. That
is the entire pipeline. Pure FARD end to end.

## Verified results

    exit: 2   — fard_main() with conditional branch (branch gate)
    exit: 42  — add2(40, 2), two FARD functions, internal call, SysV ABI
    exit: 42  — box 40, box 2, fard_add_boxed_out, unbox (40 + 2 = 42)
    exit: 42  — box 6, box 7, fard_mul_boxed_out, unbox (6 * 7 = 42)
    exit: 42  — add(10, 32) compiled from FARD source via full pipeline:
                FARD source -> fardlex -> fardparse -> fard_lower ->
                fard_ir_to_ocir -> verify -> OMIR -> x86-64 -> MH_EXECUTE

## Pipeline

Six stages, all in FARD:

    Stage 1: lower_ocir_to_omir  — slot assignment, frame sizing, param moves,
                                    branch lowering, internal and boxed calls
    Stage 2: x86_64_encode       — instruction encoding, SysV AMD64 ABI,
                                    FardVal layout, arg/param registers
    Stage 3: x86_64_fixups       — label scanning, forward branch patching
    Stage 4: x86_64_link         — symbol table, call reloc resolution
    Stage 5: macho_emit          — Mach-O x86_64 MH_OBJECT emitter + entry stub
    Stage 6: macho_exe           — Mach-O x86_64 MH_EXECUTE emitter

## MH_EXECUTE structure

    __PAGEZERO   vmaddr=0 vmsize=4GB
    __TEXT       vmaddr=0x100000000 vmsize=0x2000
      __text     fileoff=4096, entry stub + program text
    __LINKEDIT   vmaddr=0x100002000
    LC_SYMTAB    __mh_execute_header + _main + program functions
    LC_DYSYMTAB  minimal
    LC_UNIXTHREAD rip = text_vmaddr (0x100001000)

Entry stub (24 bytes, inline syscall):

    push rbp
    mov rbp, rsp
    call _fard_main          // rel32 patched at emit time
    mov rdi, rax             // exit code = return value
    mov rax, 0x2000001       // macOS exit syscall
    syscall

No _exit symbol. No dyld stub. No libSystem dependency.

## IR

### OCIR

    func_with_params(name, params, blocks)
    param(reg, ty)
    inst_imm_i64, inst_imm_bool, inst_add_i64
    inst_call_i64(dst, callee, args)         -- internal call
    inst_box_int, inst_unbox_int             -- FardVal boxing
    inst_call_add_boxed, inst_call_mul_boxed -- runtime ABI
    term_ret_i64, term_br, term_br_cond

### FardVal layout (16 bytes, repr(C))

    +0: tag     u32  — 0=INT, 1=BOOL
    +4: pad     u32  — always 0
    +8: payload u64  — i64 bits or bool 0/1

### OMIR

    prologue / epilogue
    mov_imm64, mov_stack_to_reg, mov_reg_to_stack, add_reg_stack, cmp_stack_zero
    store_param(arg_idx, slot)     -- mov [rbp+slot], arg_reg at function entry
    load_arg(arg_idx, slot)        -- mov arg_reg, [rbp+slot] before call
    write_fval_int_ops             -- write tag=0, pad=0, payload to FardVal slot
    unbox_int                      -- load payload from FardVal+8
    jne, jmp, bind_label, call_reloc
    lea_rdi_rbp, mov_rsi_rbp, mov_rdx_rbp, mov_rcx_rbp, mov_r8_rbp

## Calling Conventions

Internal (SysV AMD64): rdi rsi rdx rcx r8 r9 / return in rax

External runtime:

    fard_add_boxed_out(out: *mut FardVal, a: FardVal, b: FardVal)
    fard_mul_boxed_out(out: *mut FardVal, a: FardVal, b: FardVal)
    rdi=&dst  rsi=a.tag+pad  rdx=a.payload  rcx=b.tag+pad  r8=b.payload

## Tests

110 tests across 12 suites, all passing.

    fardrun test --program tests/test_lower_ocir_to_omir.fard   # 5
    fardrun test --program tests/test_x86_64_encode.fard        # 12
    fardrun test --program tests/test_x86_64_fixups.fard        # 5
    fardrun test --program tests/test_x86_64_link.fard          # 7
    fardrun test --program tests/test_asc7_profile.fard         # 10
    fardrun test --program tests/test_x86_64_cc.fard            # 9
    fardrun test --program tests/test_macho_emit.fard           # 20
    fardrun test --program tests/test_macho_entry.fard          # 7
    fardrun test --program tests/test_ocir_calls.fard           # 9
    fardrun test --program tests/test_boxed_arith.fard          # 6
    fardrun test --program tests/test_mul_boxed.fard            # 6
    fardrun test --program tests/test_macho_exe.fard            # 9

## Source

    src/orgntr_prim/
      ocir.fard               typed IR
      omir.fard               machine IR
      lower_ocir_to_omir.fard stage 1 lowering
      x86_64_encode.fard      stage 2 encoding
      x86_64_fixups.fard      stage 3 branch fixups
      x86_64_link.fard        stage 4 linker
      macho_emit.fard         stage 5 Mach-O object emitter (549 lines)
      macho_exe.fard          stage 6 Mach-O executable emitter (305 lines)
      asc7_profile.fard       ASC7 code_safe collapse kernel
      verify.fard             OCIR type verifier
      run_gate.fard           branch gate driver + trust record
      hash.fard               trust record construction
      target.fard             target triple

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

## Connected to FARD v0.5

FARD Prim is now connected to the FARD v0.5 compiler pipeline.

    src/orgntr_prim/
      fard_ir_to_ocir.fard      bridges v0.5 IR to OCIR (new)
      fard_source_to_native.fard  end-to-end driver: source -> binary (new)

Full pipeline:

    FARD source
      -> fardlex (tokenize)
      -> fardparse (AST)
      -> fard_lower (v0.5 IR)
      -> fard_ir_to_ocir (bridge)
      -> verify (OCIR type check)
      -> lower_ocir_to_omir (OMIR)
      -> x86_64_encode + fixups (bytes)
      -> x86_64_link (reloc resolution)
      -> macho_exe (MH_EXECUTE)
      -> binary

Usage:

    fardrun run --program programs/test_pipeline_simple.fard --out out/
    chmod +x out/fard_pipeline_test && out/fard_pipeline_test
    echo $?   # 42

## Status

- FARD v0.5.0, fardrun v1.7.1, target x86_64-apple-darwin
- Boxed arithmetic requires liborgntr_rt.a for fard_add/mul_boxed_out
- MH_EXECUTE emission does not support dylib calls — static syscall only

## Roadmap

    done   branch gate — conditional branches, native execution
    done   function arguments — SysV AMD64 param/arg moves
    done   internal FARD-to-FARD calls — resolved relocs
    done   return value ABI — rax
    done   boxed arithmetic — FardVal layout, fard_add_boxed_out (40 + 2 = 42)
    done   fard_mul_boxed_out — 6 * 7 = 42
    done   MH_EXECUTE — direct executable emission, ld removed
    next   OCIR type enforcement downstream
    then   more IR expressiveness

## Context

FARD is in Stage 8 of self-hosting: 15 stdlib modules in pure FARD,
fard_eval.fard running as a pure FARD evaluator. Stage 7 complete: native
linker resolves cross-module calls with no Rust at runtime.

FARD Prim is the bridge from that pipeline to the language compiling itself
to native x86-64 and executing correctly.

    https://github.com/mauludsadiq/FARD

## Connected to FARD v0.5

FARD Prim is now connected to the FARD v0.5 compiler pipeline.

   src/orgntr_prim/
     fard_ir_to_ocir.fard        bridges v0.5 IR to OCIR
     fard_source_to_native.fard  end-to-end driver: source -> binary

Verified native execution (23 May 2026):

    add(10, 32)  = 42   arithmetic
    max(10, 42)  = 42   if/else, CmpI64, BrCond
    fact(5)      = 120  recursion, MulI64, SubI64, CopyI64
    fib(10)      = 55   double recursion
    xs[0]        = 10   list indexing (make_list + get_index)
    xs[2]        = 30   list indexing offset
    r.a          = 42   record field access (make_rec + get_field)
    r.b          = 7    record field access second field
    s[0]         = 104  string char access ('h' from "hello")
    s[4]         = 111  string char access ('o' from "hello")
    adder(10)(32) = 64  closure call (make_closure + CallIndirect)
                        note: 64=32+32; fard_lower captures not yet emitted

IR ops supported in bridge:
    const (int, bool, str), load (CopyI64), add, sub, mul
    gt, lt, le, ge, eq, ne (CmpI64 -> Bool)
    branch/jump/patch_branch/patch_jump (flat -> block splitting)
    call (direct + indirect via global_load name map)
    make_list -> AllocHeap + StoreHeap sequence
    make_rec  -> AllocHeap + StoreHeap sequence
    make_str     -> AllocHeap + len + chars (str.char_code)
    get_index    -> LoadHeapDyn (ptr + 8 + idx*8)
    get_field    -> LoadHeapStaticIdx (compile-time field order map)
    make_closure -> MakeClosure (AllocHeap + StoreFnPtr + AbsReloc)
    call fn_r    -> CallIndirect (load fn_ptr from closure[0] + call rax)
    global_load  -> aliased to global_store src (same name)
    global_store -> filtered from output

Runtime:
    __DATA segment: 4KB bump allocator heap at 0x100002000
    fard_alloc stub: 34-byte bump allocator in __TEXT