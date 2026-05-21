# FARD Prim - Formal Specification v1

Target: x86_64-apple-darwin
FARD Prim v0.5.0 / fardrun v1.7.1

---

## Part I: OCIR Typing Rules

### 1. Types

    T ::= I64       -- 64-bit signed integer
        | Bool      -- boolean (0 or 1)
        | FardVal   -- 16-byte tagged union { tag: u32, pad: u32, payload: u64 }

Slot register r is a natural number. Each function has a finite set of slot
registers, each assigned exactly one type.

Typing environment G : Reg -> T maps slot registers to their types.

### 2. Well-Typed Module

A module M = { entry: name, funcs: [F] } is well-typed if:
- entry is in { F.name | F in funcs }
- every F in funcs is well-typed

### 3. Well-Typed Function

A function F = { name, params, blocks } is well-typed if:

**(a)** Params are well-typed: for all p in params: p.ty in { I64, Bool, FardVal }

**(b)** Build initial environment: G0 = { p.reg -> p.ty | p in params }

**(c)** Collect all instruction destinations across all blocks, extend G0 to G:
    for all inst in F: G(inst.dst) = type_of_dst(inst)

**(d)** Every block is well-typed under G

**(e)** Every dst register is written exactly once across all blocks
    (SSA-like uniqueness -- assumed by the lowering, not enforced at runtime)

### 4. Instruction Typing Rules

**[ImmI64]**

    dst : r,  val : integer literal
    -----------------------------------
    G |- inst_imm_i64(r, val) : G[r] = I64

**[ImmBool]**

    dst : r,  val : true | false
    -------------------------------------------
    G |- inst_imm_bool(r, val) : G[r] = I64
    -- Bool values are stored as I64 (0 or 1) in slots

**[AddI64]**

    G[lhs] = I64    G[rhs] = I64
    -----------------------------------------------
    G |- inst_add_i64(dst, lhs, rhs) : G[dst] = I64

**[BoxInt]**

    G[src] = I64
    ----------------------------------------------------
    G |- inst_box_int(dst, src) : G[dst] = FardVal

**[UnboxInt]**

    G[src] = FardVal
    ---------------------------------------------------
    G |- inst_unbox_int(dst, src) : G[dst] = I64
    -- Extracts payload field; tag must be TAG_INT (0)
    -- Tag check is a runtime invariant, not statically verified

**[CallI64]**

    for all i: G[args[i]] = I64
    callee names a function in the module with
      params[i].ty = I64 for all i
      return type = I64 (implicit: all functions return I64)
    ---------------------------------------------------
    G |- inst_call_i64(dst, callee, args) : G[dst] = I64

**[CallAddBoxed]**

    G[lhs] = FardVal    G[rhs] = FardVal
    ----------------------------------------------------------
    G |- inst_call_add_boxed(dst, lhs, rhs) : G[dst] = FardVal
    -- External: fard_add_boxed_out(*mut FardVal, FardVal, FardVal)
    -- Result written through output pointer; tag = TAG_INT

**[CallMulBoxed]**

    G[lhs] = FardVal    G[rhs] = FardVal
    ----------------------------------------------------------
    G |- inst_call_mul_boxed(dst, lhs, rhs) : G[dst] = FardVal

### 5. Terminator Typing Rules

**[RetI64]**

    G[src] = I64
    ---------------------------------------
    G |- term_ret_i64(src) : returns I64

**[Br]**

    to names a block label in the current function
    ---------------------------------
    G |- term_br(to) : unconditional

**[BrCond]**

    G[cond] = I64   -- condition stored as I64 (0 = false)
    then_blk and else_blk name block labels in the function
    ------------------------------------------------------------
    G |- term_br_cond(cond, then_blk, else_blk) : conditional

### 6. Type Preservation (informal)

For any well-typed OCIR function F under G, the lowering lower_func(F) produces
an OMIR function where:
- Each I64 slot maps to an 8-byte stack slot
- Each FardVal slot maps to a 16-byte stack slot
- Frame size = align16(sum of slot sizes)

Types are not carried into OMIR. Type safety at the OCIR level guarantees OMIR
will not mis-size slots or mis-route values.

---

## Part II: OMIR Operational Semantics

Machine state S = { mem: Addr -> Byte, regs: Reg -> u64 }

rbp is the frame base pointer. Stack slots are addressed as rbp + slot where
slot is negative (e.g. -8). All slot offsets are disp8: -128 <= slot <= 127.

Notation:

    mem[a..a+n]        -- n bytes starting at address a
    regs[r]            -- 64-bit value of register r
    le64(v)            -- v encoded as 8 bytes little-endian
    le32(v)            -- v encoded as 4 bytes little-endian
    le64_read(mem[a..]) -- read 8 bytes little-endian from address a

### 1. Prologue / Epilogue

**Prologue(frame_size):**

    mem[regs[rsp]-8 .. regs[rsp]-1] := le64(regs[rbp])   -- push rbp
    regs[rsp] := regs[rsp] - 8
    regs[rbp] := regs[rsp]                                -- mov rbp, rsp
    regs[rsp] := regs[rsp] - frame_size                   -- sub rsp, frame_size

**Epilogue(frame_size):**

    regs[rsp] := regs[rsp] + frame_size                   -- add rsp, frame_size
    regs[rbp] := le64_read(mem[regs[rsp]..])              -- pop rbp
    regs[rsp] := regs[rsp] + 8

### 2. Data Movement

**MovImm64(dst_reg, val):**

    regs[dst_reg] := val                                  -- mov dst, imm64

**MovStackToReg(dst_reg, src_slot):**

    regs[dst_reg] := le64_read(mem[regs[rbp] + src_slot..])   -- mov dst, [rbp+slot]

**MovRegToStack(dst_slot, src_reg):**

    mem[regs[rbp] + dst_slot .. +8] := le64(regs[src_reg])    -- mov [rbp+slot], src

**StoreParam(arg_idx, slot):**

    let r := arg_reg(arg_idx)
    mem[regs[rbp] + slot .. +8] := le64(regs[r])
    -- arg_reg: 0=rdi, 1=rsi, 2=rdx, 3=rcx, 4=r8, 5=r9

**LoadArg(arg_idx, slot):**

    let r := arg_reg(arg_idx)
    regs[r] := le64_read(mem[regs[rbp] + slot..])

### 3. Arithmetic

**AddRegStack(dst_reg, src_slot):**

    regs[dst_reg] := regs[dst_reg] + le64_read(mem[regs[rbp] + src_slot..])   -- add dst, [rbp+slot]

**CmpStackZero(src_slot):**

    flags := cmp(le64_read(mem[regs[rbp] + src_slot..]), 0)
    -- ZF=1 if slot == 0 (false), ZF=0 if slot != 0 (true)

### 4. Control Flow

**Jne(target_label):**

    if not ZF: regs[rip] := addr(target_label)            -- jne rel32 (patched)

**Jmp(target_label):**

    regs[rip] := addr(target_label)                       -- jmp rel32 (patched)

**BindLabel(label):**

    -- No machine effect.
    -- Records addr(label) = current pc for fixup pass.

**Ret:**

    regs[rip] := le64_read(mem[regs[rsp]..])
    regs[rsp] := regs[rsp] + 8                           -- ret

### 5. FardVal Operations

**WriteFvalIntOps(dst_slot, src_slot):**

    mem[regs[rbp] + dst_slot     .. +4] := le32(0)        -- tag = TAG_INT = 0
    mem[regs[rbp] + dst_slot + 4 .. +4] := le32(0)        -- pad = 0
    regs[rax] := le64_read(mem[regs[rbp] + src_slot..])
    mem[regs[rbp] + dst_slot + 8 .. +8] := le64(regs[rax]) -- payload = i64

**UnboxInt(dst_slot, src_fval_slot):**

    regs[rax] := le64_read(mem[regs[rbp] + src_fval_slot + 8..])
    mem[regs[rbp] + dst_slot .. +8] := le64(regs[rax])
    -- Runtime invariant: mem[rbp + src_fval_slot .. +4] == 0 (TAG_INT)
    -- Violation aborts (enforced by fard_*_boxed_out, not by UnboxInt)

### 6. External Calls

**LeaRdiBrp(slot):**

    regs[rdi] := regs[rbp] + slot                         -- lea rdi, [rbp+slot]

**MovRsiRbp / MovRdxRbp / MovRcxRbp / MovR8Rbp(slot):**

    regs[rsi|rdx|rcx|r8] := le64_read(mem[regs[rbp] + slot..])

**CallReloc(name):**

    mem[regs[rsp]-8..] := le64(regs[rip] + 5)            -- push return address
    regs[rsp] := regs[rsp] - 8
    regs[rip] := addr(name)                              -- call rel32 (patched)

### 7. Encoding Invariants

- All slot offsets are disp8 (-128 to 127 inclusive)
- Frame sizes are multiples of 16 (align16 enforced by slot assignment)
- Maximum frame ~128 bytes at disp8; disp32 not yet implemented

---

## Part III: ABI Specification

### 1. Internal Calling Convention (FARD-to-FARD)

Conforms to SysV AMD64 ABI for integer arguments.

**Argument registers:**

    arg[0] -> rdi    arg[1] -> rsi    arg[2] -> rdx
    arg[3] -> rcx    arg[4] -> r8     arg[5] -> r9
    arg[6+] -> stack (not yet implemented)

Argument type: I64 only. Return value: rax (64-bit integer).

**Caller sequence:**

    1. LoadArg(i, slot_of(arg[i])) for each argument
    2. CallReloc(callee_name)
    3. MovRegToStack(dst_slot, rax)

**Callee sequence:**

    1. Prologue(frame_size)
    2. StoreParam(i, slot_of(param[i])) for each parameter
    3. body
    4. MovStackToReg(rax, result_slot)
    5. Epilogue(frame_size)
    6. Ret

**Register saving:** All live values must be in stack slots before any call.
Every OCIR register has a dedicated stack slot; no value lives only in a machine
register across a call boundary. This is guaranteed by the slot assignment pass.

### 2. External Runtime Convention (FARD-to-Rust)

    pub extern "C" fn fard_add_boxed_out(
        out: *mut FardVal,    -- rdi: address of output FardVal slot
        a:   FardVal,         -- rsi: a.tag+pad  (bytes 0-7)
                              -- rdx: a.payload  (bytes 8-15)
        b:   FardVal          -- rcx: b.tag+pad  (bytes 0-7)
                              -- r8:  b.payload  (bytes 8-15)
    )

FardVal is passed by value, split across register pairs. Output is written
through the pointer in rdi. No return value in rax.

**FARD Prim call sequence for CallAddBoxed(dst, lhs, rhs):**

    lea rdi, [rbp + dst_slot]          -- &dst
    mov rsi, [rbp + lhs_slot + 0]     -- lhs.tag+pad
    mov rdx, [rbp + lhs_slot + 8]     -- lhs.payload
    mov rcx, [rbp + rhs_slot + 0]     -- rhs.tag+pad
    mov r8,  [rbp + rhs_slot + 8]     -- rhs.payload
    call fard_add_boxed_out

Same pattern applies to fard_mul_boxed_out.

After return: dst_slot contains a valid FardVal with tag=TAG_INT.
UnboxInt(result, dst) loads dst_slot+8 (payload) into result_slot.

### 3. Entry Point Convention (MH_EXECUTE)

The entry stub is the first 24 bytes of __text:

    push rbp                           -- frame setup
    mov rbp, rsp
    call _fard_main                    -- rel32 = 15 (stub_size=24, next_ip=9)
    mov rdi, rax                       -- exit code = fard_main return value
    mov rax, 0x2000001                 -- macOS exit syscall
    syscall

fard_main must have no parameters and return I64.

### 4. Stack Frame Layout

    High address
    +---------------------+
    |  return address     |  <- rsp at call site
    +---------------------+
    |  saved rbp          |  <- rbp after prologue
    +---------------------+  <- rbp (frame base)
    |  slot[0]:   -8      |  I64 or Bool (8 bytes)
    +---------------------+
    |  slot[1]:  -16      |
    +---------------------+
    |  ...                |
    +---------------------+
    |  slot[n]:   -k      |  FardVal (16 bytes)
    |             -k-8    |
    +---------------------+  <- rsp (aligned to 16)
    Low address

Slot assignment: sorted by register index ascending.
Slot offset = -(accumulated_size). Frame size = align16(total).

### 5. Symbol Table Contract

**MH_OBJECT (relocatable):**

    Defined symbols:   nlist type = 0x0F (N_EXT|N_SECT), sect=1, value=offset
    Undefined symbols: nlist type = 0x01 (N_EXT), sect=0, value=0
    Relocation: X86_64_RELOC_BRANCH (type=2), pcrel=1, len=4
    Reloc addr field: offset of rel32 operand (opcode+1, not opcode)

**MH_EXECUTE (executable):**

    __mh_execute_header  type=0x03  value=0x100000000  (required)
    _main                type=0x0F  value=text_vmaddr (0x100001000)
    program functions    type=0x0F  value=text_vmaddr + 24 + base

---

*FARD Prim v0.5.0 -- verified against fardrun v1.7.1 on x86_64-apple-darwin*
