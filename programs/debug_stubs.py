import struct, sys
f = open('out/t_str_debug', 'rb').read()
text = 4096

# str_concat stub at text+370, call (0xe8) at text+370+37=text+407
sc_call = text+407
sc_rel = struct.unpack('<i', f[sc_call+1:sc_call+5])[0]
sc_next = sc_call+5
print(f'sc: call@{sc_call-text}, rel={sc_rel}, target_offset={sc_next-text+sc_rel}')

# int_to_str stub at text+495, call (0xe8) at text+495+115=text+610
it_call = text+610
it_rel = struct.unpack('<i', f[it_call+1:it_call+5])[0]
it_next = it_call+5
print(f'it: call@{it_call-text}, rel={it_rel}, target_offset={it_next-text+it_rel}')

# alloc stub at text+669
alloc = f[text+669:text+676]
print(f'alloc@669: {list(alloc)}')
print(f'expected:  [72, 137, 216, 72, 1, 251, 195]')

# What byte is at text+610?
print(f'byte at it_call: 0x{f[it_call]:02x} (should be 0xe8)')
# Show 10 bytes around it_call
print(f'bytes {it_call-text-2}..{it_call-text+8}: {list(f[it_call-2:it_call+8])}')
