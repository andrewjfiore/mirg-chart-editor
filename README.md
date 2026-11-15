# Multi Instrument Rhythm Game (MiRG) Chart Editor

Edit the gem charts of a PS3 multi instrument rhythm game (EU title ID NPEB02398) from your own copy and pack them
so the game can load them. Try it in the browser with an original demo song: https://andrewjfiore.github.io/mirg-chart-editor/

This project is not affiliated with the game's developer or publisher, and it contains no game files: bring your own copy.

## Download
For auto-charting (gems placed for you from any audio file), run the app on your computer:

1. Download the zip: https://github.com/andrewjfiore/mirg-chart-editor/archive/refs/heads/main.zip and unzip it.
2. Double-click `Start MiRG (Mac).command` or `Start MiRG (Windows).bat`. On a Mac, the first time, right-click it and pick Open.
3. Your browser opens the editor. Click New song, pick an audio file, and leave "Place gems automatically" ticked.

The first start downloads Python, the packages and the charting models (about 2 GB); later starts take a few seconds.
Charting a song takes about 1 to 3 minutes on an Apple silicon Mac, which runs it on the GPU; on Windows it uses an NVIDIA graphics card when there is one, and the CPU (slower) when not. Without your own game files the app
runs the web version; with them it also builds game files (below).

## Run
    python3 server.py 8651      # then open http://localhost:8651/

Pick a song and a difficulty, click to add or remove gems, Save, then Build.
Build writes `work/build/USRDIR/main_ps3.hdr` and `main_ps3_10.ark`. Copy both into the installed game's
USRDIR (RPCS3: `dev_hdd0/game/NPEB02398/USRDIR`) after backing up the original `main_ps3.hdr`.

## What a song is
| file | what | tool |
|---|---|---|
| `x.mid` | source chart (standard MIDI) | `tools/chart.py` |
| `x.mid_ps3` | compiled chart the game reads (Harmonix MidiFileResource) | `tools/midps3.py` |
| `x.moggsong` / `x.moggsong_dta_ps3` | song config, text and compiled | `tools/dtb.py` |
| `x.mogg` | multitrack Ogg Vorbis with a seek map | `tools/mogg.py`, `tools/vorbis.py` |
| `x.png_ps3` | album art (DXT texture) | `tools/texdump2.py` (read only) |
| `main_ps3.hdr` + `main_ps3_N.ark` | encrypted archive index + data parts | `tools/ark.py` |

Charts: each `T# CATCH:` track has 4 difficulties x 3 lanes on MIDI notes 96 to 118 (even numbers):
note = 96 + 6*difficulty + 2*lane. Same-tick event order the compiler uses: meta, note-off, controller, note-on.

## Verified against the shipped game files (tools/test_*.py)
- Archive index: decrypt, parse, rebuild, re-encrypt = identical bytes.
- Compiled charts: read/write 35/35 identical; compiling the shipped .mid gives the shipped .mid_ps3 for 34/35
  (crazy_ride differs by one float rounding step in a tempo timestamp).
- Config: 308/308 binary configs round trip; 36/36 text configs compile to the shipped bytes.
- Chart model: .mid -> JSON -> .mid compiles to identical output for 35/35 songs.
- Audio seek maps: 20,062/20,062 entries match, except up to 3 entries at the very end of each song.

## Limits (v0)
- New songs are written and checked offline only. Whether the game lists and plays one needs a run in RPCS3.
- No custom audio yet: needs an Ogg Vorbis encoder (ffmpeg or oggenc) to make multitrack audio.
- Not yet tested in the running game (RPCS3 needs PS3 system software and the game installed).
- Game data in `work/` comes from Andrew's own copy and stays local. Never publish it.

## Auto charting (ml/)
Upload audio in the editor ("New song from audio"), choose "Add as a new song" (default) or "Replace a song" (pick the slot), and a charting model.
Pipeline (`ml/autochart.py`):
1. Demucs htdemucs_6s splits drums, bass, guitar, piano, vocals, other (`ml/separate.py`).
2. Beat This! finds beats; a constant tempo is fitted and polished on onsets (`ml/beats.py`; 28/30 game songs exact).
3. A charting model scores every 1/12-beat step per instrument; `ml/decode.py` builds Expert to the human gem
   density for that instrument, then each easier level from the one above (same steps and lanes, wider spacing).
4. Writes chart, compiled chart, 15-channel MOGG and config into `work/edits/<id>/` (built in `work/uploads/<id>/out` first, then moved, so a failed run leaves nothing half written).

## Adding a new song
Add mode makes a song id from the title (lowercase a-z and 0-9, 2 to 24 characters, starting with a letter; the API also takes `id=`).
The id cannot match a shipped song folder, song name, region name, unlock token or locale token, or a folder already in `work/edits`.
The new song borrows the world and click tracks, arena and score goal scale from a shipped donor (`donot`; the API takes `donor=`),
and uses the donor's cover art as a placeholder. `work/edits/<id>/upload.json` holds `"new": true`, the donor and the in-game description.
Build adds the 7 song files as new archive entries and edits 8 configs (`tools/songcfg.py`): one `kSongExtra` entry in World3 of
`amp_songs_config`, a `song_<id>` unlock token and a `(beat_num 0 kUnlockArena <ID>)` row in `amp_config` (open from the start, the same way
DONOTRETREAT is), and `song_<id>` plus `song_desc_<id>` in the 6 `locale_keep` files. `tools/ark.py` appends the entries and rebuilds the
bucket table (`h=(h*0x7F+c)%N` per character, N = entry count, a later entry heads its chain; matches all 1534 shipped entries).
Build then resolves every entry through the new table and reads each written file back. Delete a new song with Revert (the editor asks first).
Edit folders with an empty file are skipped and listed as incomplete.
Tests: `python3 tools/test_ark.py` and `python3 tools/test_songcfg.py work/ark`.


Two charting models, scored on the same held-out songs (`ml/evaluate.py`, report `docs/model_comparison.html`):
- Trained (`ml/model.py`, `ml/train.py`): conv + BiGRU, learned from 23 PS3 songs (clean stems) + 15 PS2 songs (Demucs stems).
- Weight-space (`ml/weightspace.py`): 664 hand-written numbers, no gradient descent.
Setup: `uv venv --python 3.12 .venv` then install torch torchaudio demucs librosa soundfile beat_this (see ml/).

## Play test
http://localhost:8651/play.html : 2D highway, Gamepad API (L1/R1/R2 or Square/Triangle/Circle lanes, D-pad/stick switch, Start pause),
menus usable with the controller alone, latency offset in Settings.

## Results 2026-11-04 (held-out PS3 songs breakforme, dreamer, magpie, synthesized2014)
| model | F1 B/I/A/E (exact step) | lane B/I/A/E |
|---|---|---|
| trained | 0.64 / 0.74 / 0.77 / 0.75 | 0.51 / 0.48 / 0.48 / 0.48 |
| weight-space | 0.54 / 0.67 / 0.78 / 0.77 | 0.38 / 0.39 / 0.42 / 0.41 |
| onset baseline | 0.32 / 0.47 / 0.60 / 0.62 | 0.34 / 0.39 / 0.40 / 0.38 |
Full report: docs/model_comparison.html. Test songs: weight-space in phantoms (Incredible) and concept (Signal Overload),
trained in necrodancer (Incredible) and redgiant (Signal Overload).

## Fun layers (weight-space, ml/weightspace_fun.py), 2026-11-04
Measured human-chart habits the plain models missed, then hand-wrote a layer for each (21 more numbers, 685 total):
motif copy (bars with matching audio get the same pattern), lane grammar (same/step/jump 27/49/24% + jump bonus on
strong onsets), burst block (no same lane within a 16th), one gem per active bar on every difficulty, loudness tilt.
Held-out test songs: repeat 0.51 -> 0.88 (human 0.91), jumps 0.08 -> 0.24 (0.27), bursts 0.02 -> 0 (0),
placement F1 0.48-0.73 -> 0.50-0.71, lane accuracy -0.03. Metrics: ml/fun_metrics.py, ml/fun_ablate.py.
Trained model now uses the same lane grammar + repeat copy (placement stays its own). Test songs: repeat 0.71 -> 0.90,
jumps 0.06 -> 0.29, same lane 0.65 -> 0.29, bursts 0.03 -> 0; F1 -0.01 to -0.02; lane accuracy 0.43-0.48 (still above weight-space).

## Web version (GitHub Pages)
`tools/build_pages.py` writes `site/`: the editor and play test plus `pages/static-api.js`, which answers the
`/api` calls in the browser. It ships one original demo song ("Glass Garden", composed and synthesized in that
file), saves edits in browser storage, and opens or downloads chart `.json` files. Build and New song from audio
stay in the local app, since they need your own copy of the game.

    python3 tools/build_pages.py              # then serve site/ with any static server

To publish: push to `main`, then in the repository settings set Pages > Build and deployment > Source to
GitHub Actions. `.github/workflows/pages.yml` builds and deploys on every push.

Game data never goes in the repo: `work/` (extracted game files and builds), `ml/data/` (features made from the
game's charts and audio) and the trained models (`ml/*.pt`, `ml/*.npz`) are in `.gitignore`. Rebuild them
locally from your own copy with the tools above.

## License
MIT, see `LICENSE`.
