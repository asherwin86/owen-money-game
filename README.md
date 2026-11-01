# Owen Money Game

A 3D money game made with Python and [Ursina](https://www.ursinaengine.org/).

Earn cash with always-available mini-game gigs, take a job at Apex Corp and climb nine ranks to CEO, sell the company, then found and grow a company of your own (and take it public for a permanent bonus).

## Download (Windows)

Grab `MoneyTycoon3D.exe` from the [latest release](../../releases/latest) and double-click it. No Python needed. Windows may show a SmartScreen warning because the exe is not code-signed: choose **More info > Run anyway**. Your progress is saved to `save.json` next to the exe. To edit the jobs, put a `data/jobs.json` next to the exe.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

On Windows you can also double-click `play.bat`. To build the exe yourself, run `build_exe.bat`.

## Controls

- **WASD** move, **Space** jump, **E** interact
- **Esc** opens the pause menu (resume or save and quit); it also closes windows and leaves mini-games

Jobs and their pay are defined in `data/jobs.json`. Progress is saved automatically to `save.json`.

## License

MIT, see [LICENSE](LICENSE).
