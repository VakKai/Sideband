"""Synthetic NRZI/G3RUH/HDLC timing and CRC checks (not an RF channel model)."""
import importlib.util,binascii
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bank',root/'replay-rsp03-clock-bank.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
rng=np.random.default_rng(816)
payload=rng.integers(0,256,250,dtype=np.uint8).tobytes()
crc=binascii.crc_hqx(payload.translate(b.d.BIT_REVERSE),0xffff)
crc=((b.d.BIT_REVERSE[crc&255]<<8)|b.d.BIT_REVERSE[crc>>8])^0xffff
bits=np.unpackbits(np.frombuffer(payload+crc.to_bytes(2,'little'),dtype=np.uint8),bitorder='little')
stuffed=[];ones=0
for bit in bits:
    stuffed.append(int(bit));ones=ones+1 if bit else 0
    if ones==5:stuffed.append(0);ones=0
flag=[0,1,1,1,1,1,1,0]
assert b.d.decode_frame(stuffed)==payload
bad=stuffed.copy();bad[10]^=1
assert b.d.decode_frame(bad) is None
wanted=flag*8+stuffed+flag*8
nrzi=[False]*17
for bit in wanted:nrzi.append(bool(bit)^nrzi[-12]^nrzi[-17])
levels=[False]
for bit in nrzi:levels.append(levels[-1] if bit else not levels[-1])
for ppm in (-1000,0,1000):
    spacing=6*(1+ppm*1e-6)
    indices=np.minimum((np.arange(int(len(levels)*spacing))/spacing).astype(int),len(levels)-1)
    y=np.where(np.asarray(levels)[indices],1.,-1.)
    recovered=b.decode(y,ppm,3.)
    assert any(f==payload for _,f in recovered),ppm
    print('250-byte synthetic packet recovered at spacing ppm',ppm)
print('Corrupted frame rejected by CRC')
