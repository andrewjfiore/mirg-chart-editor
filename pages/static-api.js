/* Static mode for GitHub Pages.
   Answers the editor's /api calls inside the browser, so editor/index.html and editor/play.html run unchanged.
   It ships one original demo song, composed and synthesized below. No game charts, audio or art are included. */
(() => {
'use strict';
const TPQ = 480, BPM = 124, BARS = 40, BAR = TPQ * 4, S16 = TPQ / 4, SR = 22050;
const KEY = 'ampStatic.', DEMO = 'demo';
const tickSec = (t) => t / TPQ * 60 / BPM;
const hz = (m) => 440 * Math.pow(2, (m - 69) / 12);
// A minor loop: Am F C G, one chord per bar
const PROG = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]];
const TRACKS = [
  { name: 'T1 CATCH:D:Drums', label: 'Drums', audio: 'drums' },
  { name: 'T2 CATCH:B:Bass', label: 'Bass', audio: 'bass' },
  { name: 'T3 CATCH:S:Synth', label: 'Synth', audio: 'synth' },
  { name: 'T4 CATCH:S:Arp', label: 'Arp', audio: 'arp' },
  { name: 'T5 CATCH:V:Vocals', label: 'Vocals', audio: 'vox' },
  { name: 'T6 CATCH:D:Hats', label: 'Hats', audio: 'hats' },
];
const on = (b, lo, hi) => b >= lo && b <= hi;
const chorus = (b) => on(b, 20, 35);
// Melody, two bars per phrase: [16th step, MIDI pitch, length in 16ths]
const MEL_A = [[0, 69, 3], [3, 72, 1], [4, 71, 2], [6, 69, 2], [8, 67, 4], [12, 69, 4], [16, 65, 3], [19, 67, 1], [20, 69, 4], [24, 72, 6]];
const MEL_B = [[0, 76, 2], [2, 74, 2], [4, 72, 4], [8, 74, 2], [10, 72, 2], [12, 71, 4], [16, 72, 3], [19, 74, 1], [20, 76, 4], [24, 79, 2], [26, 76, 6]];

/* ---------- composition: notes carry a lane and the easiest difficulty they appear on (lvl 0 to 3) ---------- */
function compose() {
  const N = TRACKS.map(() => []);
  const add = (k, bar, step, o) => N[k].push(Object.assign({ t: bar * BAR + step * S16, d: S16 }, o));
  for (let b = 0; b < BARS; b++) {
    const ch = PROG[b % 4], root = ch[0];
    // drums: kick L, snare M, crash on section starts (sound only, it shares the downbeat)
    if (b < 4) { add(0, b, 0, { lane: 0, lvl: 0, s: 'kick' }); add(0, b, 8, { lane: 0, lvl: 1, s: 'kick' }); }
    else if (b <= 37) {
      add(0, b, 0, { lane: 0, lvl: 0, s: 'kick' });
      add(0, b, 4, { lane: 1, lvl: 1, s: 'snare' });
      if (b <= 35) add(0, b, 6, { lane: 0, lvl: 3, s: 'kick' });
      add(0, b, 8, { lane: 0, lvl: 2, s: 'kick' });
      add(0, b, 12, { lane: 1, lvl: 1, s: 'snare' });
      if (chorus(b) && b % 2 === 1) add(0, b, 14, { lane: 2, lvl: 3, s: 'snare' });
      if (b === 4 || b === 20 || b === 36) add(0, b, 0, { gem: false, s: 'crash' });
    }
    // bass: root L, fifth M, octave R
    if (on(b, 4, 37)) {
      for (const [st, iv, lane, lvl] of [[0, 0, 0, 0], [3, 12, 2, 3], [6, 7, 1, 2], [8, 0, 0, 1], [10, 12, 2, 3], [12, 7, 1, 2], [14, 12, 2, 3]]) {
        add(1, b, st, { lane, lvl, p: root - 24 + iv, d: S16 * 2 });
      }
    }
    // synth stabs on the off beats
    if (on(b, 4, 39)) {
      const steps = chorus(b) ? [[2, 2], [6, 0], [10, 2], [11, 3], [14, 1]] : [[2, 2], [6, 0], [10, 2], [14, 1]];
      for (const [st, lvl] of steps) add(2, b, st, { lane: (st >> 2) % 3, lvl, chord: ch.map((n) => n + 12), d: S16 * 2 });
    }
    // arp: chord tones in sixteenths
    if (on(b, 12, 35)) {
      const pat = [0, 1, 2, 1];
      for (let st = 0; st < 16; st++) {
        const i = pat[st % 4];
        add(3, b, st, { lane: i, lvl: st === 0 ? 0 : st % 4 === 0 ? 1 : st % 2 === 0 ? 2 : 3, p: ch[i] + 12 + (i === 2 && st % 8 === 6 ? 12 : 0) });
      }
    }
    // vocal lead: a four bar tune, verse and chorus
    if ((on(b, 8, 15) || chorus(b)) && b % 2 === 0) {
      const mel = b % 4 === 0 ? MEL_A : MEL_B;
      for (const [st, p, len] of mel) {
        add(4, b, st, { lane: p < 70 ? 0 : p < 74 ? 1 : 2, lvl: st % 8 === 0 ? 0 : len >= 3 ? 1 : st % 4 === 0 ? 2 : 3, p: p + (chorus(b) ? 0 : -12), d: S16 * len });
      }
    }
    // hats: closed L, mid M, open R
    if (on(b, 4, 35)) {
      for (let st = 0; st < 16; st += chorus(b) ? 1 : 2) {
        if (st % 2 === 1 && st % 4 !== 3) continue;
        const open = st % 8 === 6;
        add(5, b, st, { lane: open ? 2 : st % 4 === 0 ? 0 : 1, lvl: st % 8 === 0 ? 0 : st % 4 === 0 ? 1 : st % 2 === 0 ? 2 : 3, s: open ? 'ohat' : 'hat' });
      }
    }
  }
  return N;
}
let NOTES = null;
const notes = () => NOTES || (NOTES = compose());

function demoSong() {
  const tracks = TRACKS.map((tr, k) => {
    const gems = [];
    for (const n of notes()[k]) if (n.gem !== false) for (let d = n.lvl; d <= 3; d++) gems.push([n.t, d, n.lane, 120, 100]);
    gems.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return { index: k + 1, name: tr.name, kind: 'catch', label: tr.label, gems };
  });
  return {
    id: DEMO,
    meta: { title: 'Glass Garden', artist: 'Demo song', bpm: BPM, section_start_bars: [1, 17, 33], song_info: [], enable_order: [1, 2, 3, 4, 5, 6], preview_start_ms: 0, preview_length_ms: 15000 },
    tpq: TPQ, tempos: [[0, Math.round(60e6 / BPM)]], timesig: [[0, 4, 4]], world: [], length_ticks: BARS * BAR, edited: false, tracks,
  };
}

/* ---------- synthesis: one channel per track plus a pad, rendered offline and handed over as WAV ---------- */
async function renderDemo() {
  const CH = TRACKS.length + 1, len = Math.ceil((tickSec(BARS * BAR) + 2) * SR);
  const ctx = new OfflineAudioContext(CH, len, SR);
  ctx.destination.channelInterpretation = 'discrete';
  const merger = ctx.createChannelMerger(CH); merger.connect(ctx.destination);
  const bus = [];
  for (let k = 0; k < CH; k++) { const g = ctx.createGain(); g.channelCount = 1; g.channelCountMode = 'explicit'; g.connect(merger, 0, k); bus.push(g); }
  const noise = ctx.createBuffer(1, SR, SR); const nd = noise.getChannelData(0);
  let seed = 7; for (let i = 0; i < nd.length; i++) { seed = (seed * 16807) % 2147483647; nd[i] = seed / 1073741823.5 - 1; }
  const env = (t0, peak, a, hold, r) => { const g = ctx.createGain(); g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(peak, t0 + a); g.gain.setValueAtTime(peak, t0 + a + hold); g.gain.exponentialRampToValueAtTime(0.0001, t0 + a + hold + r); return g; };
  const filt = (type, f, q) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q || 0.7; return b; };
  const osc = (type, f, t0, t1, detune) => { const o = ctx.createOscillator(); o.type = type; o.frequency.value = f; if (detune) o.detune.value = detune; o.start(t0); o.stop(t1); return o; };
  const hit = (out, t0, dur, vol, chain) => { const s = ctx.createBufferSource(); s.buffer = noise; const g = env(t0, vol, 0.002, 0, dur); let n = s; for (const f of chain) { n.connect(f); n = f; } n.connect(g); g.connect(out); s.start(t0); s.stop(t0 + dur + 0.05); };
  notes().forEach((list, k) => {
    for (const n of list) {
      const t0 = tickSec(n.t), dur = tickSec(n.d);
      if (k === 0 || k === 5) {
        if (n.s === 'kick') { const o = osc('sine', 150, t0, t0 + 0.4); o.frequency.exponentialRampToValueAtTime(42, t0 + 0.14); const g = env(t0, 0.9, 0.003, 0.02, 0.28); o.connect(g); g.connect(bus[k]); }
        else if (n.s === 'snare') { hit(bus[k], t0, 0.17, 0.55, [filt('bandpass', 1900, 0.8)]); const o = osc('triangle', 190, t0, t0 + 0.15); const g = env(t0, 0.35, 0.002, 0, 0.1); o.connect(g); g.connect(bus[k]); }
        else if (n.s === 'crash') hit(bus[k], t0, 1.4, 0.22, [filt('highpass', 5000)]);
        else if (n.s === 'hat') hit(bus[k], t0, 0.045, 0.28, [filt('highpass', 8000)]);
        else if (n.s === 'ohat') hit(bus[k], t0, 0.24, 0.24, [filt('highpass', 7000)]);
      } else if (k === 1) {
        const o = osc('sawtooth', hz(n.p), t0, t0 + dur + 0.1), lp = filt('lowpass', 520, 5), g = env(t0, 0.42, 0.005, dur * 0.6, 0.12);
        o.connect(lp); lp.connect(g); g.connect(bus[k]);
      } else if (k === 2) {
        const lp = filt('lowpass', 2400, 1.5), g = env(t0, 0.11, 0.004, dur * 0.4, 0.16); lp.connect(g); g.connect(bus[k]);
        for (const m of n.chord) for (const dt of [-8, 8]) osc('sawtooth', hz(m), t0, t0 + dur + 0.25, dt).connect(lp);
      } else if (k === 3) {
        const o = osc('square', hz(n.p), t0, t0 + 0.2), lp = filt('lowpass', 3200), g = env(t0, 0.12, 0.003, 0, 0.13);
        o.connect(lp); lp.connect(g); g.connect(bus[k]);
      } else if (k === 4) {
        const o = osc('sawtooth', hz(n.p), t0, t0 + dur + 0.2), vib = osc('sine', 5.5, t0, t0 + dur + 0.2), vd = ctx.createGain();
        vd.gain.value = 6; vib.connect(vd); vd.connect(o.detune);
        const f1 = filt('bandpass', 900, 1.6), f2 = filt('lowpass', 2600), g = env(t0, 0.5, 0.03, Math.max(0, dur - 0.06), 0.18);
        o.connect(f1); f1.connect(f2); f2.connect(g); g.connect(bus[k]);
      }
    }
  });
  // pad bed on the last channel, the part the game would call background
  for (let b = 0; b < BARS; b++) {
    const t0 = tickSec(b * BAR), dur = tickSec(BAR);
    const lp = filt('lowpass', 1400), g = env(t0, 0.07, 0.25, dur - 0.3, 0.6); lp.connect(g); g.connect(bus[CH - 1]);
    for (const m of PROG[b % 4]) osc('triangle', hz(m), t0, t0 + dur + 0.7).connect(lp);
  }
  const buf = await ctx.startRendering();
  // keep the full mix under full scale, then write 16-bit WAV
  const chans = []; for (let c = 0; c < CH; c++) chans.push(buf.getChannelData(c));
  let peak = 0;
  for (let i = 0; i < len; i++) { let s = 0; for (let c = 0; c < CH; c++) s += chans[c][i]; if (Math.abs(s) > peak) peak = Math.abs(s); }
  const gain = peak > 0.95 ? 0.95 / peak : 1;
  const out = new ArrayBuffer(44 + len * CH * 2), v = new DataView(out);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); v.setUint32(4, 36 + len * CH * 2, true); str(8, 'WAVEfmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, CH, true); v.setUint32(24, SR, true); v.setUint32(28, SR * CH * 2, true); v.setUint16(32, CH * 2, true); v.setUint16(34, 16, true);
  str(36, 'data'); v.setUint32(40, len * CH * 2, true);
  let o = 44;
  for (let i = 0; i < len; i++) for (let c = 0; c < CH; c++) { const s = Math.max(-1, Math.min(1, chans[c][i] * gain)); v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true); o += 2; }
  return out;
}
let wavP = null;
const demoWav = () => wavP || (wavP = renderDemo());
const demoInfo = () => ({ tracks: TRACKS.map((t, i) => ({ name: t.audio, channels: [i] })).concat([{ name: 'background', channels: [TRACKS.length] }]), pans: new Array(TRACKS.length + 1).fill(0), vols: new Array(TRACKS.length + 1).fill(0), sample_rate: SR });

/* ---------- storage: saved edits and chart files the visitor opened ---------- */
const get = (k, d) => { try { const v = localStorage.getItem(KEY + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
const put = (k, v) => { try { localStorage.setItem(KEY + k, JSON.stringify(v)); return true; } catch (e) { return false; } };
const drop = (k) => { try { localStorage.removeItem(KEY + k); } catch (e) { /* storage unavailable */ } };
const opened = () => get('opened', []);
// audio files for new songs live in IndexedDB; they are too big for localStorage
const idb = () => new Promise((res, rej) => {
  const r = indexedDB.open('ampStatic', 1);
  r.onupgradeneeded = () => r.result.createObjectStore('files');
  r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
});
async function fileSet(k, v) {
  const db = await idb();
  return new Promise((res, rej) => { const tx = db.transaction('files', 'readwrite'); tx.objectStore('files').put(v, k); tx.oncomplete = () => res(true); tx.onerror = () => rej(tx.error); });
}
async function fileGet(k) {
  try {
    const db = await idb();
    return await new Promise((res, rej) => { const q = db.transaction('files').objectStore('files').get(k); q.onsuccess = () => res(q.result || null); q.onerror = () => rej(q.error); });
  } catch (e) { return null; }
}
// one track named bg_click: both pages play it as background that no chart track owns, so it is always heard
const mixInfo = () => ({ tracks: [{ name: 'bg_click', channels: [0, 1, 2, 3, 4, 5, 6, 7] }], pans: new Array(8).fill(0), vols: new Array(8).fill(0), sample_rate: 44100 });
// auto-charted songs: one channel per chart track in order, then background
const stemInfo = (names) => ({ tracks: names.map((name, i) => ({ name, channels: [i] })), pans: new Array(names.length).fill(0), vols: new Array(names.length).fill(0), sample_rate: 32000 });
function baseSong(id) {
  if (id === DEMO) return demoSong();
  const s = get('song.' + id, null);
  if (!s) throw new Error('Unknown song ' + id);
  return Object.assign(s, { id });
}
function songWithEdit(id) {
  const s = baseSong(id), e = get('edit.' + id, null);
  if (e) { const by = new Map(e.tracks.map((t) => [t.index, t.gems])); for (const t of s.tracks) if (by.has(t.index)) t.gems = by.get(t.index); }
  s.edited = !!e;
  return s;
}
function songList() {
  const row = (id, m) => ({ id, title: m.title, artist: m.artist || '', bpm: m.bpm || null, edited: !!get('edit.' + id, null), uploaded: false, model: null });
  return [row(DEMO, demoSong().meta)].concat(opened().map((o) => row(o.id, o)));
}

/* ---------- the fetch stand-in ---------- */
const json = (o, status) => new Response(JSON.stringify(o), { status: status || 200, headers: { 'Content-Type': 'application/json' } });
const LOCAL_ONLY = 'This needs the local app with your own copy of the game. The web version edits the demo song and chart files you open.';
async function api(path, method, body) {
  const id = decodeURIComponent(path.split('/').pop() || '');
  if (path === '/api/songs') return json(songList());
  if (path.startsWith('/api/song/')) {
    if (method === 'POST') {
      const b = JSON.parse(body || '{}');
      if (!put('edit.' + id, { tracks: b.tracks || [] })) return json({ error: 'Browser storage is full or blocked, so the edit was not saved. Use Download chart to keep it.' }, 507);
      return json({ ok: true, gems: (b.tracks || []).reduce((n, t) => n + (t.gems || []).length, 0) });
    }
    return json(songWithEdit(id));
  }
  if (path.startsWith('/api/revert/')) { drop('edit.' + id); return json({ ok: true }); }
  if (path.startsWith('/api/play_info/') || path.startsWith('/api/play_audio/')) {
    const info = path.startsWith('/api/play_info/');
    if (id === DEMO) return info ? json(demoInfo()) : new Response((await demoWav()).slice(0), { headers: { 'Content-Type': 'audio/wav' } });
    const f = await fileGet('audio.' + id);
    if (!f) return json({ error: 'No audio for this chart. Charts opened from a file have no audio.' }, 404);
    const names = get('song.' + id, {}).audio_tracks;
    return info ? json(names ? stemInfo(names) : mixInfo()) : new Response(await f.arrayBuffer(), { headers: { 'Content-Type': f.type || 'application/octet-stream' } });
  }
  return json({ error: LOCAL_ONLY }, 501);
}
const realFetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  const url = new URL(typeof input === 'string' ? input : input.url, location.href);
  const i = url.pathname.indexOf('/api/');
  if (i < 0) return realFetch(input, init);
  return api(url.pathname.slice(i), ((init && init.method) || 'GET').toUpperCase(), init && init.body).catch((e) => json({ error: e.message }, 500));
};

/* ---------- editor additions: open and download chart files, hide what needs the local app ---------- */
function editorUi() {
  const bar = document.getElementById('bar1'), link = document.getElementById('playLink');
  if (!bar || !link) return;
  const css = document.createElement('style');
  css.textContent = '#upBtn,#buildBtn{display:none!important}'
    + '#staticTip{position:fixed;right:14px;bottom:40px;z-index:30;max-width:330px;padding:9px 30px 10px 12px;font:12px/1.4 Tahoma,Verdana,sans-serif;color:#000;'
    + 'background:#ffffe1;border:1px solid #000;border-radius:7px;box-shadow:3px 3px 6px rgba(0,0,0,.35)}'
    + '#staticTip b{display:block;margin-bottom:3px}#staticTip a{color:#0033cc}'
    + '#staticTip button{position:absolute;right:5px;top:5px;min-width:0;width:18px;height:18px;padding:0;font-size:11px;line-height:1}';
  document.head.appendChild(css);
  const file = document.createElement('input'); file.type = 'file'; file.accept = '.json,application/json'; file.hidden = true;
  const openB = document.createElement('button'); openB.textContent = 'Open chart'; openB.title = 'Open a chart file (.json) saved from this editor';
  const dlB = document.createElement('button'); dlB.textContent = 'Download chart'; dlB.title = 'Save the chart on screen, with unsaved changes, as a .json file';
  const newB = document.createElement('button'); newB.textContent = 'New song'; newB.title = 'Start a blank chart over your own audio file';
  link.before(newB);
  link.after(openB, dlB, file);
  openB.addEventListener('click', () => file.click());
  newB.addEventListener('click', newSong);
  file.addEventListener('change', async () => {
    const f = file.files[0]; file.value = '';
    if (!f) return;
    try {
      const s = JSON.parse(await f.text());
      if (!s || !Array.isArray(s.tracks) || !s.tracks.every((t) => Array.isArray(t.gems)) || !s.meta) throw new Error('This file is not a chart from this editor.');
      s.tpq = s.tpq || 480; s.tempos = s.tempos || [[0, 500000]]; s.timesig = s.timesig || [[0, 4, 4]]; s.world = s.world || [];
      const id = 'file_' + Date.now().toString(36);
      if (!put('song.' + id, s)) throw new Error('Browser storage is full or blocked.');
      put('opened', opened().concat([{ id, title: s.meta.title || f.name, artist: s.meta.artist || '', bpm: s.meta.bpm || null }]));
      await refreshSongs(); await switchSong(id);
    } catch (e) { msg('Could not open ' + f.name + ': ' + e.message, 'err'); }
  });
  dlB.addEventListener('click', () => {
    if (!S.song) return;
    const out = JSON.parse(JSON.stringify(S.song));
    const by = new Map(S.tracks.map((t) => [t.index, [].concat(t.byDiff[0], t.byDiff[1], t.byDiff[2], t.byDiff[3])]));
    for (const t of out.tracks) if (by.has(t.index)) t.gems = by.get(t.index);
    delete out.edited;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], { type: 'application/json' }));
    a.download = (out.meta.title || 'chart').replace(/[^\w.-]+/g, '_') + '.chart.json';
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  });
  if (!get('tipClosed', false)) {
    mlCheck().then((helper) => {
      const tip = document.createElement('div'); tip.id = 'staticTip'; tip.setAttribute('role', 'status');
      tip.innerHTML = helper
        ? '<b>Auto-charting is on</b>Click New song and pick an audio file: this computer splits the instruments and places the gems.'
        : '<b>Web version</b>Edit the demo song, start a New song over your own audio, or open a chart file. To have gems placed for you automatically, '
          + '<a target="_blank" rel="noopener" href="' + REPO + '#install-adds-auto-charting">download the app</a>.';
      tip.insertAdjacentHTML('beforeend', '<button type="button" aria-label="Close">x</button>');
      tip.querySelector('button').addEventListener('click', () => { tip.remove(); put('tipClosed', true); });
      document.body.appendChild(tip);
    });
  }
}
/* ---------- New song: a blank chart over the visitor's own audio file ---------- */
const NEW_TRACKS = [['T1 CATCH:D:Drums', 'Drums'], ['T2 CATCH:B:Bass', 'Bass'], ['T3 CATCH:S:Synth', 'Synth'], ['T4 CATCH:G:Guitar', 'Guitar'], ['T5 CATCH:V:Vocals', 'Vocals'], ['T6 CATCH:S:Synth 2', 'Synth 2']];
const REPO = 'https://github.com/andrewjfiore/mirg-chart-editor';
// the downloaded app answers /ml/ping; the hosted web version does not
let mlP = null;
const mlCheck = () => mlP || (mlP = fetch('/ml/ping', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).then((j) => (j && j.ok && j.model ? j : null)).catch(() => null));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function autoChart(f, t, a) {
  const q = new URLSearchParams({ title: t, artist: a, name: f.name });
  let j = await (await fetch('/ml/chart?' + q, { method: 'POST', body: f })).json();
  while (!j.error && !j.done) {
    msg(j.stage + ' ' + Math.round((j.progress || 0) * 100) + '%', 'busy');
    await sleep(1000);
    j = await (await fetch('/ml/job/' + j.id, { cache: 'no-store' })).json();
  }
  if (j.error) throw new Error(String(j.error).replace(/^\w+\(['"]?|['"]?\)$/g, ''));
  return { song: j.result, audio: await (await fetch('/ml/audio/' + j.id)).blob() };
}
async function newSong() {
  const helper = await mlCheck();
  const form = document.createElement('div'); form.className = 'upGrid';
  const row = (label, input) => { const l = document.createElement('label'); l.textContent = label; form.append(l, input); return input; };
  const inp = (type, attrs) => Object.assign(document.createElement('input'), { type }, attrs);
  const fileIn = row('Audio', inp('file', { accept: 'audio/*,.wav,.mp3,.ogg,.flac,.aif,.aiff' }));
  const title = row('Title', inp('text', { placeholder: 'Required' }));
  const artist = row('Artist', inp('text'));
  const bpm = row('BPM', inp('number', { min: 40, max: 300, step: 1, value: 120 }));
  const bpmLabel = bpm.previousSibling;
  const auto = inp('checkbox', { checked: !!helper, disabled: !helper });
  const autoLbl = document.createElement('label'); autoLbl.className = 'chk'; autoLbl.append(auto, ' Place gems automatically');
  row('Gems', autoLbl);
  const note = document.createElement('div'); note.className = 'upNote';
  const body = document.createElement('div'); body.append(form, note);
  const sync = () => {
    bpm.hidden = bpmLabel.hidden = auto.checked;
    if (auto.checked) note.textContent = 'This computer finds the beat, splits the instruments and charts every track. Takes about 1 to 3 minutes.';
    else if (helper) note.textContent = 'You get six empty tracks to fill in with clicks.';
    else { note.textContent = 'You get six empty tracks to fill in with clicks. To have gems placed automatically, '; const l = document.createElement('a'); l.href = REPO + '#install-adds-auto-charting'; l.target = '_blank'; l.rel = 'noopener'; l.textContent = 'download the app'; note.append(l, '.'); }
  };
  auto.addEventListener('change', sync); sync();
  fileIn.addEventListener('change', () => { const f = fileIn.files[0]; if (f && !title.value.trim()) title.value = f.name.replace(/\.[^.]+$/, ''); });
  const r = await ask({ title: 'New song', body, buttons: [{ label: 'Create', value: 'ok', primary: true }, { label: 'Cancel', value: 'cancel', cancel: true }] });
  if (r !== 'ok') return;
  const f = fileIn.files[0], t = title.value.trim(), b = Math.round(+bpm.value), a = artist.value.trim();
  if (!f) return msg('Choose an audio file to make a new song.', 'err');
  if (!t) return msg('Give the new song a title.', 'err');
  if (!auto.checked && !(b >= 40 && b <= 300)) return msg('BPM has to be between 40 and 300.', 'err');
  const btn = [...document.querySelectorAll('#bar1 button')].find((x) => x.textContent === 'New song');
  if (btn) btn.disabled = true;
  try {
    let song, audio = f;
    if (auto.checked) ({ song, audio } = await autoChart(f, t, a));
    else {
      msg('Reading ' + f.name + '...', 'busy');
      const dur = (await new OfflineAudioContext(1, 1, 44100).decodeAudioData(await f.arrayBuffer())).duration;
      song = {
        meta: { title: t, artist: a, bpm: b, section_start_bars: [], song_info: [], enable_order: [1, 2, 3, 4, 5, 6] },
        tpq: TPQ, tempos: [[0, Math.round(60e6 / b)]], timesig: [[0, 4, 4]], world: [], length_ticks: (Math.ceil(dur * b / 60 / 4) + 1) * BAR,
        tracks: NEW_TRACKS.map(([name, label], i) => ({ index: i + 1, name, kind: 'catch', label, gems: [] })),
      };
    }
    const id = 'new_' + Date.now().toString(36);
    await fileSet('audio.' + id, audio);
    if (!put('song.' + id, song)) throw new Error('Browser storage is full or blocked.');
    put('opened', opened().concat([{ id, title: t, artist: a, bpm: song.meta.bpm }]));
    await refreshSongs(); await switchSong(id);
    msg(auto.checked ? 'Charted ' + t + '. Edit any gem, then Save.' : 'Created ' + t + '. Click in a lane to add gems, then Save.', 'ok');
  } catch (e) { msg('Could not make the song from ' + f.name + ': ' + (e && e.message ? e.message : 'the browser cannot read this audio file'), 'err'); }
  finally { if (btn) btn.disabled = false; }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', editorUi); else editorUi();
window.__ampStatic = { demoSong, demoWav };
})();
