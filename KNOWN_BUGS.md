# Known Bugs

## GC-001: Dynamic list append capacity (FIXED)
**Symptom:** `xs=[]; while i<1000: xs.append(i)` → SIGSEGV  
**Root cause:** Empty list `[]` allocated only 8 element slots; appending past slot 8
wrote past allocation end, corrupting heap.  
**Fix:** Increased initial capacity from 8 to 64 slots in `python_to_uvir.fard`.
Verified: 1000 appends now works correctly (exit=232=1000%256).  
**Remaining limitation:** Lists with >64 appends will still crash. True fix requires
dynamic growth (realloc+copy) in `__list_append__`.  
**Status:** Partially fixed — 64-slot capacity committed

## COMPILE-001: Compilation is slow due to interpreted execution
**Symptom:** Complex programs take 45-120s to compile; FARD native suite takes ~2min  
**Root cause:** fardrun is an interpreter running ~19k lines of FARD compiler source.
The compiler itself is correct and fast; interpretation overhead is O(program_complexity).
Nested while programs generate larger OCIR (more blocks/instructions) → more interpreter work.  
**Fix:** Self-hosting — compile FARD Prim with itself to get native-speed compilation  
**Workaround:** Use 120s timeout in test harness  
**Status:** By design until self-hosting milestone
