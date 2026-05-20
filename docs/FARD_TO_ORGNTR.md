# FARD to ORGNTR Transition Plan

## Current native proof

The Rust ORGNTR repo has proven:

```text
OCIR branch gate -> x86_64 Mach-O object -> link -> run -> 2
```

and:

```text
out.o has LC_BUILD_VERSION
```

## FARD Prim purpose

FARD Prim moves the authority point upward:

```text
Rust OCIR structs -> FARD OCIR records
Rust verifier     -> FARD verifier
Rust trust record -> FARD trust record
```

Once this layer is fixed, Rust is no longer the semantic authority.

Rust becomes only the temporary object-emission backend until FARD can emit object bytes.

## Required next modules

### 1. OMIR

File:

```text
src/orgntr_prim/omir.fard
```

OMIR should contain explicit machine-relevant operations:

```text
MovImm64
MovStackToReg
MovRegToStack
AddRegStack
CmpStackZero
Jne
Jmp
Ret
CallReloc
```

### 2. Lowering

File:

```text
src/orgntr_prim/lower_ocir_to_omir.fard
```

### 3. x86_64 encoder

File:

```text
src/orgntr_prim/x86_64_encode.fard
```

### 4. Mach-O writer

File:

```text
src/orgntr_prim/macho.fard
```

First target:

```text
x86_64-apple-darwin
```

## Acceptance test for FARD object emitter

```bash
cc -arch x86_64 -o run host.c out.o target/x86_64-apple-darwin/debug/liborgntr_rt.a
./run
otool -l out.o | rg "LC_BUILD_VERSION"
```

Expected:

```text
2
cmd LC_BUILD_VERSION
```
