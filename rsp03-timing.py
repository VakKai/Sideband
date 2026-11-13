#!/usr/bin/env python3
"""Experimental feed-forward symbol clock recovery; no station inputs in decoder."""
import importlib.util
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
spec = importlib.util.spec_from_file_location('diagnostic', Path(__file__).with_name('replay-rsp03.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def recover(iq, shift_hz=0, references=None):
    if shift_hz:
        iq = iq * np.exp(2j*np.pi*shift_hz*np.arange(len(iq))/d.RATE)
    filtered = fftconvolve(iq, d.FILTER, mode='same')
    discriminator = np.angle(filtered[1:] * filtered[:-1].conj())
    y = np.convolve(discriminator, [.5,.5], mode='same')
    # Transition energy supplies a clock tone independent of bit decisions.
    # Estimate its phase every 20 ms; smooth through interpolation rather than
    # restarting the clock at block boundaries. Weak/noisy windows still run;
    # CRC validates outputs, and no reference data select clock parameters.
    block = 1152
    nblocks = len(y)//block
    if nblocks < 2:
        return []
    energy = np.diff(y, prepend=y[0])**2
    carrier = np.exp(-2j*np.pi*np.arange(block)/6)
    tone = np.sum(energy[:nblocks*block].reshape(-1, block) * carrier, axis=1)
    transition_phase = np.unwrap(-np.angle(tone)) * 6/(2*np.pi)
    centers = np.arange(nblocks)*block + block/2
    nominal = np.arange(24, len(y)-24, 6.)
    clock = np.interp(nominal, centers, transition_phase)
    found = []
    # Fixed offsets cover discriminator/filter convention and pulse asymmetry;
    # all are specified a priori and applied equally to every chunk.
    for offset in (0., 1., 2., 3., 4., 5.):
        positions = nominal + clock + offset
        levels = np.interp(positions, np.arange(len(y)), y)>0
        nrzi = levels[1:] == levels[:-1]
        bits = nrzi[17:] ^ nrzi[5:-12] ^ nrzi[:-17]
        flags=np.flatnonzero(np.convolve(bits.astype(np.int8),[-1,1,1,1,1,1,1,-1],mode='valid')==6)
        for left,right in zip(flags,flags[1:]):
            if right-left>2500:
                continue
            frame=d.decode_frame(bits[left+8:right])
            if frame is not None:
                t=positions[left+18]/d.RATE
                if not any(frame==f and abs(t-s)<.002 for s,f in found):
                    found.append((t,frame))
    return sorted(found)
