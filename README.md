# Owen Money Game

A 3D money game made with Python and [Ursina](https://www.ursinaengine.org/).

Earn cash with always-available mini-game gigs, deliver food across a 6 km open world of freeways, highways and bridges with GPS, take a job at Apex Corp and climb nine ranks to CEO, sell the company, then found and grow a company of your own (and take it public for a permanent bonus).

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

A new always-available job in the Gig Plaza. Start a shift and drive a company car around a 6 km open world: more than 30,000 houses with named streets and real addresses, cut by a winding **river**, two elevated **freeways**, two **highways** and arterial boulevards.

- You have to get past the obstacles to reach the house. The river can only be crossed on its five bridges. Freeways have walls and can only be entered by **on-ramps** and left by exits, while ordinary streets pass beneath them at underpasses. Highways have median walls with only a few crossings.
- Orders pop up: press **Y** to accept, **N** to skip. Pick up the food at a restaurant, then deliver it to the customer's address.
- **GPS** finds the fastest route and talks you through it ("Take the ramp to Interstate 5", "Cross Harbor Bridge", "Take the exit toward Route 12"), with a route line on the road, a minimap, a whole-world map (**M**) and a destination picker (**G**).
- Pay depends on distance, speed, tips and **food quality**; crashes shake the food and driving into the river ruins it. Your **rating** nudges your pay up or down.
- Drive carefully around the AI traffic. Upgrade the **delivery car** in the shop to go from 100 km/h up to **200 km/h**, and the **insulated bag** to carry more orders at once.
- Park at the Dash Eats Depot and press **E** to end the shift.

## Controls

Everything can be played with a keyboard and mouse **or a game controller** (Xbox-style pads and most others that Windows recognises; plug it in before or during the game).

| Action | Keyboard | Controller |
| --- | --- | --- |
| Walk / look | WASD, mouse | Left stick / right stick |
| Jump | Space | A |
| Interact | E | X |
| Menus | mouse | D-pad or left stick to choose, A select, B close |
| Pause menu | Esc | Start |
| Sorting, memory, reaction mini-games | 1-4 / Space | B, A, X, Y (they match the colours) |
| Typing and maths mini-games | type | on-screen keys: D-pad / stick to move, A to press |
| Drive | WASD, Space handbrake | Left stick steer, RT gas, LT brake/reverse, LB handbrake |
| Accept / skip order | Y / N | X / B |
| GPS destination, map, reset car | G, M, R | Y, Back, RB |

Keyboard controls:

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
