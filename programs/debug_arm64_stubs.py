import struct
f = open('out/t_str_debug', 'rb').read()
text = 4096
sc_start = 256; it_start = sc_start+200; alloc_at = 240

# Find bl instructions (0x94...) in each stub
for name, start, size in [('sc', sc_start, 200), ('it', it_start, 256)]:
    for off in range(0, size, 4):
        pos = text + start + off
        w = struct.unpack('<I', f[pos:pos+4])[0]
        if (w >> 26) == 0x25:  # bl opcode
            imm26 = w & 0x3ffffff
            if imm26 & 0x2000000: imm26 -= 0x4000000
            target = start + off + imm26*4
            print(f'{name} bl@{off}: 0x{w:08x}, target={target} (should={alloc_at})')

alloc = list(f[text+alloc_at:text+alloc_at+16])
print(f'alloc@{alloc_at}: {alloc}')
print(f'sc start bytes: {list(f[text+sc_start:text+sc_start+4])}')
print(f'it start bytes: {list(f[text+it_start:text+it_start+4])}')
