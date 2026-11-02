# Owen Money Game

A 3D money game made with Python and [Ursina](https://www.ursinaengine.org/).

Earn cash with always-available mini-game gigs, drive a delivery car around a huge city with GPS, take a job at Apex Corp and climb nine ranks to CEO, sell the company, then found and grow a company of your own (and take it public for a permanent bonus).

## Download (Windows)

Grab `MoneyTycoon3D.exe` from the [latest release](../../releases/latest) and double-click it. No Python needed. Windows may show a SmartScreen warning because the exe is not code-signed: choose **More info > Run anyway**. Your progress is saved to `save.json` next to the exe. To edit the jobs, put a `data/jobs.json` next to the exe.

### Updates

The game checks GitHub for a newer version when it starts and offers to update itself. The download is checked against the size and SHA-256 checksum GitHub publishes for the release, then replaces the exe and restarts the game. Choose **Check for updates** or turn the automatic check off in the pause menu (Esc). Updating needs write access to the folder the exe is in. Version 1.0.0 had no updater, so download 1.1.0 by hand once.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

On Windows you can also double-click `play.bat`. To build the exe yourself, run `build_exe.bat`.

## Food Delivery

A new always-available job in the Gig Plaza. Start a shift and drive a company car around a city of over 5,000 houses with named streets and real addresses.

- Orders pop up: press **Y** to accept, **N** to skip. Pick up the food at a restaurant, then deliver it to the customer's address.
- **GPS** turn-by-turn directions, a glowing route line on the road, a minimap (**M** for the whole-city map) and a destination picker (**G**).
- Pay depends on distance, speed, tips and **food quality**; crashes shake the food. Your **rating** nudges your pay up or down.
- Drive carefully around the AI traffic. Upgrade the **delivery car** and the **insulated bag** in the shop (a bigger bag carries more orders at once).
- Park at the Dash Eats Depot and press **E** to end the shift.

## Controls

- **WASD** move, **Space** jump, **E** interact
- While driving: **WASD** or arrows drive, **Space** handbrake, **R** reset car onto the road
- **Esc** opens the pause menu (resume or save and quit); it also closes windows and leaves mini-games

### Releasing a new version (maintainers)

1. Bump `VERSION` in `version.py`, run `build_exe.bat`, and sign the exe if you have a certificate.
2. Create a GitHub release whose tag matches (for example `v1.2.0`) and attach `MoneyTycoon3D.exe` under exactly that name.
3. Players with 1.1.0 or newer are offered the update the next time they start the game.

Jobs and their pay are defined in `data/jobs.json`. Progress is saved automatically to `save.json`.

## License

MIT, see [LICENSE](LICENSE).
