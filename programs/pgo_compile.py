#!/usr/bin/env python3
# pgo_compile.py -- Profile-guided compilation driver
#
# Phase 1: ./instrumented_binary 2> profile.raw
# Phase 2: python3 pgo_compile.py 'src_string' profile.raw output
#
# Gets function names from FARD compiler, builds hotness map by name,
# then calls emit_guided with the hotness map.

import sys, struct, subprocess, os, tempfile, json

def parse_profile(path):
    with open(path,"rb") as f: data = f.read()
    h = {}
    for i in range(min(len(data)//8, 512)):
        v = struct.unpack_from('<q', data, i*8)[0]
        if v > 0:
            h[i//100] = h.get(i//100, 0) + v
    return h  # func_idx -> count

def get_func_names(src_str):
    # Run FARD to get function names in OCIR order
    driver = '''import("../src/orgntr_prim/fardlex") as lex
import("../src/orgntr_prim/fardparse") as par
import("../src/orgntr_prim/ast_licm") as licm
import("../src/orgntr_prim/ast_unroll") as unroll
import("../src/orgntr_prim/fard_lower") as lower
import("../src/orgntr_prim/fard_ir_to_ocir") as bridge
import("../src/orgntr_prim/ocir_opt") as opt
import("../src/orgntr_prim/ocir_sccp") as sccp
import("../src/orgntr_prim/ocir_sr") as sr
import("../src/orgntr_prim/ocir_inline") as inl
import("../src/orgntr_prim/ocir_gvn") as gvn
import("../src/orgntr_prim/ocir_dfe") as dfe
import("std/list") as list
let src = SRC_PLACEHOLDER
let parsed = par.parse_module(lex.tokenize(src), 0)
let lm = licm.licm_module(parsed.node)
let u = unroll.unroll_module(lm)
let ir = lower.lower_program(u)
let ocir = bridge.lower_module(ir)
let p1 = opt.opt_module(sccp.sccp_module(opt.opt_module(ocir)))
let p2 = sr.sr_module(p1)
let p3 = inl.inline_module(p2)
let p4 = dfe.dfe_module(opt.opt_module(gvn.gvn_module(sccp.sccp_module(opt.opt_module(p3)))))
list.map(p4.funcs, fn(f){ f.name })
'''.replace('SRC_PLACEHOLDER', json.dumps(src_str))

    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard', dir='tests',
                                     delete=False, prefix='pgo_names_') as f:
        f.write(driver)
        path = f.name
    result = subprocess.run(
        ["fardrun","run","--program",path,"--out","/tmp/pgo_names_out"],
        capture_output=True, text=True)
    os.unlink(path)
    data = json.loads(open("/tmp/pgo_names_out/result.json").read())
    return data["result"]

def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} 'fard_src' profile.raw output", file=sys.stderr)
        sys.exit(1)

    src_str, profile_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    hotness_idx = parse_profile(profile_path)
    print(f"Raw hotness by index: {hotness_idx}")

    func_names = get_func_names(src_str)
    print(f"Function order: {func_names}")

    # Map index -> name -> count
    hotness_by_name = {}
    for idx, name in enumerate(func_names):
        hotness_by_name[name] = hotness_idx.get(idx, 0)
    print(f"Hotness by name: {hotness_by_name}")

    # Build FARD record literal
    pairs = [f'  "{k}": {v}' for k,v in hotness_by_name.items()]
    hotness_literal = "{\n" + ",\n".join(pairs) + "\n}"

    # Ensure \n in src is a FARD string escape, not double-escaped
    fard_src = json.dumps(src_str.replace("\\n", "\n"))
    driver = f'''import("../src/orgntr_prim/fard_source_to_native_pgo") as pgo
let src = {fard_src} in
let hotness_map = {hotness_literal} in
pgo.emit_guided(src, hotness_map, {json.dumps(output_path)})
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.fard', dir='tests',
                                     delete=False, prefix='pgo_guided_') as f:
        f.write(driver)
        driver_path = f.name

    print("Running guided compilation...")
    result = subprocess.run(
        ["fardrun","run","--program",driver_path,"--out","/tmp/pgo_guided_out"],
        capture_output=True, text=True)
    os.unlink(driver_path)

    if os.path.exists(output_path):
        os.chmod(output_path, 0o755)
        size = os.path.getsize(output_path)
        print(f"Written: {output_path} ({size} bytes)")
    else:
        print("Output not created:", result.stderr[:300], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
