#!/usr/bin/env python3
"""PS2 (SCUS-97258) AUDIO/*.STR decoder and chart-alignment checker.

Layout found empirically (see detect_layout, `ps2audio.py layout`), identical for all 26 files:
  no file header, raw signed 16-bit little-endian PCM, 2 channels, 512-byte interleave blocks
  (256 samples of channel 0, then 256 samples of channel 1, ...), 48000 Hz.
The sample rate is not stored in the file. It is fixed by matching the beat period of the audio
(spectral-flux autocorrelation) against the chart tempo: `ps2audio.py rate`.

Commands (python tools/ps2audio.py <cmd> -h):
  layout  FILE            score every (channels, interleave) candidate by stream smoothness
  rate    [--songs ..]    beat-period match of audio vs chart tempo for candidate sample rates
  decode  FILE OUT.wav    decode one STR to a float WAV
  verify  [--songs ..]    gem-time spectral-flux check per CATCH track (lag -20..20 frames)
  map                     STR x chart matrix: proves the STR -> song mapping
  stems   [--songs ..]    write work/ps2/stems/<song>/mix.wav + map.json
"""
import argparse, json, os, re, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PS2 = os.path.join(ROOT, 'work', 'ps2')
AUDIO_DIR = os.path.join(PS2, 'mnt', 'AUDIO')       # read only disc image mount
SONGS_DIR = os.path.join(PS2, 'ark', 'songs')
STEMS_DIR = os.path.join(PS2, 'stems')

# Decode parameters found by detect_layout / estimate_rate (defaults; every function can override).
DEFAULT_CHANNELS = 2
DEFAULT_INTERLEAVE = 512     # bytes per channel block
DEFAULT_RATE = 48000

# STR file -> song folder. The names are 8.3 truncations; verified by `map` (diagonal of the matrix).
STR_TO_SONG = {
    'BALDWINB': 'baldwinbros', 'BASELINE': 'baseline', 'BLINK182': 'blink182', 'BOWIE': 'bowie',
    'BT': 'bt', 'DIESELBO': 'dieselboy', 'DRUMNBAS': 'drumnbass', 'GARBAGE': 'garbage',
    'GEDGRIME': 'gedgrimes', 'HOUSE': 'house', 'KOMPUTER': 'komputer', 'LOGAN7': 'logan7',
    'MANCHILD': 'manchild', 'MEKON': 'mekon', 'OUTTHEBO': 'outthebox', 'PAPAROAC': 'paparoach',
    'PINK': 'pink', 'POD': 'pod', 'ROCKIT': 'rockit', 'ROCKSTAR': 'rockstar', 'RUNDMC': 'rundmc',
    'SHADES_O': 'shades_of_blue', 'SLIPKNOT': 'slipknot', 'SPASTIK': 'spastik',
    'SUPERSPR': 'supersprode', 'WEEZER': 'weezer',
}


# ---------------------------------------------------------------- decoding
def read_raw(path):
    return np.fromfile(path, dtype='<i2')


def deinterleave(raw, channels=DEFAULT_CHANNELS, interleave=DEFAULT_INTERLEAVE):
    """int16 samples (file order) -> int16 array (frames, channels). A trailing partial group is dropped."""
    bs = interleave // 2                      # samples per block
    group = bs * channels
    n = (raw.size // group) * group
    a = raw[:n].reshape(-1, channels, bs)     # (group, channel, sample in block)
    return np.ascontiguousarray(a.transpose(0, 2, 1).reshape(-1, channels))


def decode(path, channels=None, interleave=None, rate=None):
    """STR path -> (float32 array frames x channels in [-1, 1), sample rate)."""
    channels = channels or DEFAULT_CHANNELS
    interleave = interleave or DEFAULT_INTERLEAVE
    rate = rate or DEFAULT_RATE
    pcm = deinterleave(read_raw(path), channels, interleave)
    return pcm.astype(np.float32) / 32768.0, rate


def interleave_spikes(raw, period=16384):
    """Byte offsets (mod `period`) where adjacent samples jump far more than elsewhere = block boundaries.
    Returns (sorted [(byte_offset, jump / median jump)], median jump)."""
    P = period // 2
    n = (raw.size // P) * P
    a = raw[:n].reshape(-1, P).astype(np.float32)
    d = np.abs(np.diff(a, axis=1)).mean(axis=0)       # d[i] = |x[i+1]-x[i]| averaged over every period
    med = float(np.median(d))
    pos = np.where(d > 1.5 * med)[0]
    return sorted(((int(i) + 1) * 2, float(d[i] / med)) for i in pos), med


def channel_continuity(raw, interleave, channels=range(1, 13), maxblocks=60000):
    """For each channel count N: median of |first sample of block k+N - last sample of block k| divided by the mean
    in-block step. About 1 when block k+N continues block k (right N); several times larger for a wrong N."""
    bs = interleave // 2
    start = (raw.size // 3 // bs) * bs
    nb = min(maxblocks, (raw.size - start) // bs)
    a = raw[start:start + nb * bs].reshape(nb, bs).astype(np.float64)
    step = np.abs(np.diff(a, axis=1)).mean(axis=1)
    out = {}
    for n in channels:
        x = np.abs(a[n:, 0] - a[:-n, -1])
        out[n] = float(np.median(x / (step[n:] + 1.0)))
    return out


def detect_layout(raw):
    """(channels, interleave_bytes, report). Interleave = smallest block-boundary spike offset;
    channels = the N whose same-channel blocks are most continuous (smallest N on ties within 5 percent)."""
    sp, med = interleave_spikes(raw)
    big = [o for o, r in sp if r > 1.5]
    inter = min(big)
    cont = channel_continuity(raw, inter)
    best = min(cont.values())
    n = min(k for k, v in cont.items() if v <= best * 1.05)
    return n, inter, {'spikes': sp[:12], 'median_jump': med, 'continuity': cont}


# ---------------------------------------------------------------- chart
def load_chart(mid_path):
    """Returns dict: tpq, tempo_ticks, tempo_us, tracks {n: {'name', 'gems': [(tick, diff, lane)]}} for T1..T6 CATCH."""
    import mido
    m = mido.MidiFile(mid_path)
    tempos = {}
    tracks = {}
    for t in m.tracks:
        tick = 0
        name = ''
        gems = []
        for e in t:
            tick += e.time
            if e.type == 'set_tempo':
                tempos[tick] = e.tempo
            elif e.type == 'track_name' and not name:
                name = e.name
            elif e.type == 'note_on' and e.velocity > 0 and 96 <= e.note <= 118 and (e.note - 96) % 2 == 0:
                d, lane = divmod((e.note - 96) // 2, 3)
                gems.append((tick, d, lane))
        mm = re.match(r'^T([1-6])\s+catch', name, re.I)
        if mm and int(mm.group(1)) not in tracks:
            tracks[int(mm.group(1))] = {'name': name.strip(), 'gems': gems}
    tk = sorted(tempos)
    if not tk or tk[0] != 0:
        tk = [0] + tk
        tempos.setdefault(0, 500000)
    return {'tpq': m.ticks_per_beat, 'tempo_ticks': np.array(tk, dtype=np.int64),
            'tempo_us': np.array([tempos[x] for x in tk], dtype=np.float64), 'tracks': tracks}


def ticks_to_seconds(chart, ticks):
    """Tick -> seconds through the full tempo map (all tempo changes)."""
    tt, us, tpq = chart['tempo_ticks'], chart['tempo_us'], chart['tpq']
    seg_sec = np.concatenate([[0.0], np.cumsum(np.diff(tt) * us[:-1] / 1e6 / tpq)])
    ticks = np.asarray(ticks, dtype=np.int64)
    i = np.searchsorted(tt, ticks, side='right') - 1
    return seg_sec[i] + (ticks - tt[i]) * us[i] / 1e6 / tpq


def dominant_bpm(chart):
    tt, us = chart['tempo_ticks'], chart['tempo_us']
    last = max([max((g[0] for g in tr['gems']), default=0) for tr in chart['tracks'].values()] + [int(tt[-1]) + 1])
    dur = np.diff(np.concatenate([tt, [last]]))
    return 60e6 / us[int(np.argmax(dur))]


def expert_times(chart, track=None):
    """Sorted unique Expert (difficulty 3) gem times in seconds for one track (1..6) or all."""
    ks = [track] if track else sorted(chart['tracks'])
    ticks = sorted({g[0] for k in ks if k in chart['tracks'] for g in chart['tracks'][k]['gems'] if g[1] == 3})
    return ticks_to_seconds(chart, ticks) if ticks else np.zeros(0)


# ---------------------------------------------------------------- features
def spectral_flux(x, hop=256, nfft=512):
    """Half-wave rectified log-magnitude spectral flux. flux[i] = rise from STFT frame i-1 to i; frame i is
    centred on sample i*hop, so an onset at sample t lights up around frame t/hop (minus about half a window)."""
    from scipy.fft import rfft
    x = np.asarray(x, dtype=np.float32)
    nfr = len(x) // hop + 1
    xp = np.pad(x, (nfft // 2, nfft + hop))
    win = np.hanning(nfft).astype(np.float32)
    flux = np.zeros(nfr, dtype=np.float32)
    prev = None
    step = 4096
    for s in range(0, nfr, step):
        e = min(nfr, s + step)
        idx = (np.arange(s, e)[:, None] * hop) + np.arange(nfft)[None, :]
        mag = np.log1p(1000.0 * np.abs(rfft(xp[idx] * win, axis=1))).astype(np.float32)
        if prev is not None:
            mag = np.vstack([prev, mag])
            d = np.diff(mag, axis=0)
            flux[s:e] = np.maximum(d, 0).sum(axis=1)
        else:
            d = np.diff(mag, axis=0)
            flux[s + 1:e] = np.maximum(d, 0).sum(axis=1)
        prev = mag[-1:]
    return flux


def lag_curve(flux, times, rate, hop=256, lags=range(-20, 21)):
    g = np.round(np.asarray(times) * rate / hop).astype(np.int64)
    out = []
    for L in lags:
        i = g + L
        i = i[(i >= 0) & (i < len(flux))]
        out.append(float(flux[i].mean()) if len(i) else float('nan'))
    return np.array(out)


def gem_check(flux, times, rate, hop=256, lags=range(-20, 21), nrand=5000, nnull=200, seed=0):
    """Best lag (frames), gem/random flux ratio at that lag and at lag 0, and a z score against random gem sets
    (same count, same lag search) so the maximum over 41 lags is not credited as signal."""
    lags = list(lags)
    g_all = np.round(np.asarray(times) * rate / hop).astype(np.int64)
    g = g_all[g_all < len(flux) - 20]            # gems past the end of the audio cannot be scored
    if len(g) < 8:
        return None
    times = g * hop / rate
    cur = lag_curve(flux, times, rate, hop, lags)
    k = int(np.nanargmax(cur))
    lo, hi = int(g.min()), int(g.max())
    rng = np.random.default_rng(seed)
    base = float(flux[rng.integers(lo, hi, nrand)].mean())
    nulls = []
    for _ in range(nnull):
        r = rng.integers(lo, hi, len(g))
        nulls.append(max(float(flux[np.clip(r + L, 0, len(flux) - 1)].mean()) for L in lags))
    z = (cur[k] - np.mean(nulls)) / (np.std(nulls) + 1e-12)
    return {'lag': lags[k], 'ratio': cur[k] / base, 'ratio0': cur[lags.index(0)] / base, 'z': float(z), 'n': int(len(g)), 'n_total': int(len(g_all))}


# ---------------------------------------------------------------- rate
def estimate_rate(mono, bpm, candidates=(22050, 24000, 32000, 44100, 48000), hop=128, nfft=512):
    """Score each candidate rate: mean flux autocorrelation at 1..8 beat periods (tolerance +-0.4 percent)."""
    fl = spectral_flux(mono, hop=hop, nfft=nfft)
    fl = fl - fl.mean()
    n = len(fl)
    F = np.fft.rfft(fl, 2 * n)
    ac = np.fft.irfft(F * np.conj(F))[:n]
    ac /= ac[0]
    res = {}
    for sr in candidates:
        per = 60.0 / bpm * sr / hop
        vals = []
        for k in range(1, 9):
            c = per * k
            lo, hi = int(np.floor(c * 0.996)), int(np.ceil(c * 1.004)) + 1
            if hi < n:
                vals.append(ac[lo:hi].max())
        res[sr] = float(np.mean(vals)) if vals else float('nan')
    return res


# ---------------------------------------------------------------- helpers
def song_paths(name):
    stem = [k for k, v in STR_TO_SONG.items() if v == name or k == name.upper()][0]
    return os.path.join(AUDIO_DIR, stem + '.STR'), os.path.join(SONGS_DIR, STR_TO_SONG[stem], STR_TO_SONG[stem] + '_g.mid'), stem


def pick(songs):
    allsongs = sorted(STR_TO_SONG.values())
    if not songs:
        return allsongs
    want = [s.strip() for s in songs.split(',')]
    for w in want:
        if w not in allsongs:
            sys.exit('unknown song %s; choose from %s' % (w, ', '.join(allsongs)))
    return want


def write_wav(path, data, rate):
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, data, rate, subtype='FLOAT')


# ---------------------------------------------------------------- commands
def cmd_layout(a):
    raw = read_raw(a.file)
    n, b, rep = detect_layout(raw)
    print('file %s: %d bytes, size mod 2048 = %d' % (a.file, raw.size * 2, (raw.size * 2) % 2048))
    print('block boundary jumps (byte offset mod 16384, jump / median step), first 8:',
          ['%d:%.1fx' % (o, r) for o, r in rep['spikes'][:8]])
    print('same-channel continuity at interleave %d by channel count (1.0 = continuous):' % b)
    print('  ' + '  '.join('N=%d:%.2f' % (k, v) for k, v in rep['continuity'].items()))
    print('layout: %d channels, interleave %d bytes' % (n, b))


def cmd_rate(a):
    cands = (22050, 24000, 32000, 44100, 48000)
    print('Candidate sample rates. Beat = flux autocorrelation at 1..8 beat periods (rates 2x apart are not separable by it).')
    print('Gem = best gem/random flux ratio over lag -20..20 when gem times are mapped to samples at that rate (decides).')
    print('%-15s %6s | beat: %s | gem: %s | pick  audio_s  last_gem_s' % (
        'song', 'bpm', ' '.join('%5d' % c for c in cands), ' '.join('%5d' % c for c in cands)))
    for s in pick(a.songs):
        sp, mp, _ = song_paths(s)
        ch = load_chart(mp)
        bpm = dominant_bpm(ch)
        x, _ = decode(sp)
        mono = x.mean(axis=1)
        beat = estimate_rate(mono, bpm, cands)
        fl = spectral_flux(mono)
        tm = expert_times(ch)
        gem = {c: best_ratio(fl, tm, c) for c in cands}
        pick_ = max(gem, key=lambda k: gem[k])
        print('%-15s %6.1f | %s | %s | %5d %7.1f %7.1f' % (
            s, bpm, ' '.join('%5.2f' % beat[c] for c in cands), ' '.join('%5.2f' % gem[c] for c in cands),
            pick_, x.shape[0] / pick_, tm.max()), flush=True)


def cmd_decode(a):
    x, sr = decode(a.file, a.channels, a.interleave, a.rate)
    write_wav(a.out, x, sr)
    print('%s: %d frames x %d ch at %d Hz (%.2f s)' % (a.out, x.shape[0], x.shape[1], sr, x.shape[0] / sr))


def verify_song(s, hop=256):
    sp, mp, stem = song_paths(s)
    x, sr = decode(sp)
    ch = load_chart(mp)
    sigs = {'L': x[:, 0], 'R': x[:, 1], 'mid': x.mean(axis=1), 'side': (x[:, 0] - x[:, 1]) / 2}
    fl = {k: spectral_flux(v, hop=hop) for k, v in sigs.items()}
    res = {'song': s, 'str': stem + '.STR', 'channels': x.shape[1], 'rate': sr, 'seconds': x.shape[0] / sr, 'tracks': {}}
    for t in range(1, 7):
        tm = expert_times(ch, t)
        res['tracks'][t] = {'name': ch['tracks'].get(t, {}).get('name'), 'n_gems': int(len(tm)),
                            **{k: gem_check(f, tm, sr, hop) for k, f in fl.items()}}
    res['all'] = {k: gem_check(f, expert_times(ch), sr, hop) for k, f in fl.items()}
    return res


def cmd_verify(a):
    results = []
    print('%-15s %2s %5s | %s' % ('song', 'ch', 'rate', 'per track (mid mix): best lag frames, gem/random flux ratio at best lag, z'))
    for s in pick(a.songs):
        r = verify_song(s)
        results.append(r)
        cells = []
        for t in range(1, 7):
            c = r['tracks'][t]['mid']
            cells.append('T%d %+3d %.2f z%4.1f' % (t, c['lag'], c['ratio'], c['z']) if c else 'T%d  n/a' % t)
        print('%-15s %2d %5d | %s' % (s, r['channels'], r['rate'], ' | '.join(cells)), flush=True)
    if a.json:
        json.dump(results, open(a.json, 'w'), indent=1)
    return results


def best_ratio(flux, times, rate, hop=256):
    """Max over lag -20..20 of mean flux at the gem times, divided by mean flux at random times in the gem span."""
    g = np.round(np.asarray(times) * rate / hop).astype(np.int64)
    g = g[g < len(flux) - 20]
    if len(g) < 8:
        return float('nan')
    base = float(flux[np.random.default_rng(0).integers(int(g.min()), int(g.max()), 5000)].mean())
    return float(np.nanmax(lag_curve(flux, g * hop / rate, rate, hop))) / base


def cmd_map(a):
    names = pick(a.songs)
    flux, times, rate = {}, {}, DEFAULT_RATE
    for s in names:
        sp, mp, _ = song_paths(s)
        x, _ = decode(sp)
        flux[s] = spectral_flux(x.mean(axis=1))
        times[s] = expert_times(load_chart(mp))
    print('rows = STR audio, columns = chart. Cell = best gem/random flux ratio over lag -20..20 (all Expert gems).')
    print('%-15s %s' % ('', ' '.join('%4s' % n[:4] for n in names)))
    wrong = 0
    for s in names:
        row = [best_ratio(flux[s], times[c], rate) for c in names]
        best = names[int(np.argmax(row))]
        wrong += best != s
        print('%-15s %s  best=%s%s' % (s, ' '.join('%4.2f' % v for v in row), best, '' if best == s else '  <-- MISMATCH'))
    print('%d of %d rows peak on their own chart' % (len(names) - wrong, len(names)))


def cmd_stems(a):
    """mix.wav (the STR itself: one stereo mix) + map.json. track1..6.wav are not written: the STR has no per-track audio."""
    for s in pick(a.songs):
        sp, mp, stem = song_paths(s)
        x, sr = decode(sp)
        out = os.path.join(STEMS_DIR, s)
        write_wav(os.path.join(out, 'mix.wav'), x, sr)
        ch = load_chart(mp)
        v = verify_song(s)
        keep = lambda c: None if c is None else {k: (round(c[k], 3) if isinstance(c[k], float) else c[k]) for k in c}
        info = {'str': stem + '.STR', 'song': s, 'channels': int(x.shape[1]), 'sample_rate': sr,
                'interleave': DEFAULT_INTERLEAVE, 'sample_format': 's16le, no header',
                'frames': int(x.shape[0]), 'seconds': round(x.shape[0] / sr, 3),
                'chart_tracks': {str(k): t['name'] for k, t in sorted(ch['tracks'].items())},
                'track_channels': {},          # no CATCH track has its own channel
                'extra_channels': [0, 1],      # left, right of the single stereo mix
                'note': 'The STR holds one stereo mix (channel 0 left, channel 1 right). No per-track stems are stored in '
                        'it, so track1..6.wav are not written.',
                'alignment': {'all_expert_gems_mid': keep(v['all']['mid']),
                              'per_track_mid': {str(t): keep(v['tracks'][t]['mid']) for t in range(1, 7)},
                              'per_track_L': {str(t): keep(v['tracks'][t]['L']) for t in range(1, 7)},
                              'per_track_R': {str(t): keep(v['tracks'][t]['R']) for t in range(1, 7)},
                              'method': 'log-magnitude spectral flux, hop 256 samples at the native rate, lag -20..20 frames, '
                                        'ratio = mean flux at Expert gem times / mean flux at random times'}}
        json.dump(info, open(os.path.join(out, 'map.json'), 'w'), indent=1)
        print('wrote', out, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    q = sp.add_parser('layout'); q.add_argument('file'); q.set_defaults(f=cmd_layout)
    q = sp.add_parser('rate'); q.add_argument('--songs'); q.set_defaults(f=cmd_rate)
    q = sp.add_parser('decode'); q.add_argument('file'); q.add_argument('out')
    q.add_argument('--channels', type=int); q.add_argument('--interleave', type=int); q.add_argument('--rate', type=int)
    q.set_defaults(f=cmd_decode)
    q = sp.add_parser('verify'); q.add_argument('--songs'); q.add_argument('--json'); q.set_defaults(f=cmd_verify)
    q = sp.add_parser('map'); q.add_argument('--songs'); q.set_defaults(f=cmd_map)
    q = sp.add_parser('stems'); q.add_argument('--songs'); q.set_defaults(f=cmd_stems)
    a = p.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
