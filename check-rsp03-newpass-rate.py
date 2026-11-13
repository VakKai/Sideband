"""Record numerical sample-rate evidence for the second October development pass."""
import hashlib,json
from pathlib import Path
import h5py,numpy as np
root=Path(__file__).resolve().parent
rows=[]
for obs in ['12511719','12511720']:
    iq=root/'replays/rsp03'/f'iq_{obs}.raw'
    metadata=root/'replays/rsp03/metadata'
    with h5py.File(metadata/f'{obs}.h5') as f:
        freq=f['waterfall/frequency'][:];t=f['waterfall/relative_time'][:]
        spacing=float(np.median(np.diff(freq)))
        rate=spacing*len(freq)
        assert np.allclose(np.diff(freq),spacing) and rate==57600
        duration=iq.stat().st_size/4/rate
        assert 0<duration-float(t[-1])<.25
        rows.append(dict(observation=obs,sample_rate=rate,frequency_bins=len(freq),numeric_frequency_bin_spacing=spacing,numeric_frequency_min=float(freq[0]),numeric_frequency_max=float(freq[-1]),waterfall_last_relative_seconds=float(t[-1]),iq_duration_seconds=duration,iq_sha256=hashlib.sha256(iq.read_bytes()).hexdigest(),artifact_url=(metadata/f'{obs}-artifact-url.txt').read_text().strip(),note='Frequency dataset labels say kHz, but numerical values are Hz, consistent with rendered +/-28.8 kHz plot and time/sample-count check. ADC metadata 1 MHz is upstream, not the I/Q dump rate.'))
(root/'results/rsp03-rate-12511719-12511720.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
