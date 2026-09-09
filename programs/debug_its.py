import struct
d = open('out/t_its_debug', 'rb').read()
it_call = 4096 + 495 + 115
rel = struct.unpack('<i', d[it_call+1:it_call+5])[0]
next_ip = it_call + 5
alloc = 4096 + 669
print('it_rel32:', rel, 'should_be:', alloc - next_ip)
print('it_start_bytes:', list(d[4096+495:4096+500]))
