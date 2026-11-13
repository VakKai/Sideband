"""Check frequency-estimator units/sign and detector preservation of known recoveries."""
import importlib.util, csv
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve, firwin
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tracking',root/'replay-rsp03-tracking.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rng=np.random.default_rng(482)
n=57600*10
noise=rng.normal(size=n)+1j*rng.normal(size=n)
x=fftconvolve(noise,firwin(129,3000,fs=57600),mode='same')
for offset in [-500,0,500]:
    shifted=x*np.exp(2j*np.pi*offset*np.arange(n)/57600)
    ratio,center=m.spectrum(shifted)
    estimate=float(np.mean(center[5:-5]))
    assert abs(estimate-offset)<30,(offset,estimate)
    print('Injected Hz:',offset,'estimated Hz:',round(estimate,2))
for obs in ['12511021','12511022']:
    base=list(csv.DictReader((root/'results'/f'rsp03-whole-{obs}.csv').open()))
    packets=list(csv.DictReader((root/'results'/f'rsp03-tracking-{obs}-packets.csv').open()))
    raw=[r for r in packets if r['mode']=='raw']
    assert len(base)==len(raw)
    for row in base:
        assert any(r['sha256']==row['payload_sha256'] and abs(float(r['seconds'])-float(row['seconds_from_iq_start']))<.002 for r in raw)
    print(obs, 'detector preserved every baseline occurrence')
