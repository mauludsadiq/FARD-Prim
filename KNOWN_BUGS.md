# Known Bugs

## GC-001: Dynamic list append crashes at 1000+ elements
**Symptom:** `xs=[]; while i<1000: xs.append(i)` → SIGSEGV  
**Root cause:** Precise GC ptrmask is computed at alloc time based on initial size.
When `__list_append__` grows the backing store (realloc-style), the new allocation
gets a different ptrmask, but the old pointer stored in the caller's heap cell still
points to the old (now GC-scanned-incorrectly) object.  
**Workaround:** Use fixed-size list literals: `xs=[i,i+1,i+2]`  
**Status:** Not yet fixed

## COMPILE-001: Nested while loops take >60s to compile
**Symptom:** `while i<5: while j<i: ...` takes >60s in compile_python.py  
**Root cause:** Unknown — likely exponential behavior in one of the optimization
passes (LICM or loop fusion) when processing nested loop CFG structure.  
**Workaround:** Use 120s timeout  
**Status:** Not yet investigated
