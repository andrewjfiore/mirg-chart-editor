# Multi Instrument Rhythm Game (MiRG) Chart Editor

Make and edit gem charts for a PS3 multi instrument rhythm game, play test them, and turn any audio file into a chart automatically.

Try it in your browser: https://andrewjfiore.github.io/mirg-chart-editor/

## Install (adds auto-charting)
Mac, in Terminal:

    curl -fsSL https://raw.githubusercontent.com/andrewjfiore/mirg-chart-editor/main/install.sh | bash

Windows, in PowerShell:

    irm https://raw.githubusercontent.com/andrewjfiore/mirg-chart-editor/main/install.ps1 | iex

The editor opens in your browser. Click New song, pick an audio file and keep "Place gems automatically" ticked.
The first start downloads about 2 GB. To start again, double-click Start MiRG in the "MiRG Chart Editor" folder in
your home folder. To update, paste the line again.

## Edit the game's own songs
You need your own copy of the game (EU title ID NPEB02398).

1. Copy the game's `USRDIR` folder (RPCS3: `dev_hdd0/game/NPEB02398/USRDIR`) to `work/pkg/USRDIR` in the app folder.
2. In the app folder run `.venv/bin/python tools/ark.py extract work/pkg/USRDIR work/ark` (Windows: `.venv\Scripts\python.exe`).
3. Start the app, edit, Save, then Build.
4. Back up the game's `main_ps3.hdr`, then copy the files Build lists from `work/build/USRDIR` into the game's `USRDIR`.

Not affiliated with the game's developer or publisher. No game files are included.

## License
MIT
