# Known Bugs

## GC-001: Dynamic list append crashes at 1000+ elements
**Symptom:** `xs=[]; while i<1000: xs.append(i)` → SIGSEGV  
**Root cause:** Precise GC ptrmask is computed at alloc time based on initial size.
When `__list_append__` grows the backing store (realloc-style), the new allocation
gets a different ptrmask, but the old pointer stored in the caller's heap cell still
points to the old (now GC-scanned-incorrectly) object.  
**Workaround:** Use fixed-size list literals: `xs=[i,i+1,i+2]`  
**Status:** Not yet fixed

## COMPILE-001: Compilation is slow due to interpreted execution
**Symptom:** Complex programs take 45-120s to compile; FARD native suite takes ~2min  
**Root cause:** fardrun is an interpreter running ~19k lines of FARD compiler source.
The compiler itself is correct and fast; interpretation overhead is O(program_complexity).
Nested while programs generate larger OCIR (more blocks/instructions) → more interpreter work.  
**Fix:** Self-hosting — compile FARD Prim with itself to get native-speed compilation  
**Workaround:** Use 120s timeout in test harness  
**Status:** By design until self-hosting milestone
