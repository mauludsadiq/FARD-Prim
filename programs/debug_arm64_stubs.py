import struct
f = open('out/t_str_debug', 'rb').read()
text = 4096
sc_start = 256; it_start = 464; alloc_at = 240

for name, stub_start, bl_off in [('sc', sc_start, 68), ('it', it_start, 164)]:
    pos = text + stub_start + bl_off
    w = struct.unpack('<I', f[pos:pos+4])[0]
    imm26 = w & 0x3ffffff
    if imm26 & 0x2000000: imm26 -= 0x4000000
    target = stub_start + bl_off + imm26*4
    print(f'{name} bl: 0x{w:08x}, target_text_offset={target} (should={alloc_at})')

alloc = list(f[text+alloc_at:text+alloc_at+16])
print(f'alloc: {alloc}')
print(f'expected: {[169,2,9,170,19,1,19,170,0,192,95,214,0,0,0,0]}')
