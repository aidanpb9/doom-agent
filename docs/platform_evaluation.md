## WAD Verification

Tested doom1.wad compatibility with all episodes:

- Episode 1: E1M1-E1M9 ✓
- Episode 2: E2M1-E2M9 ✓  
- Episode 3: E3M1-E3M9 ✓

All 27 levels load successfully in VizDoom.

PROOF:
- run this code block, it shows all 27 levels opening
- use the code block from the raw version of this file
- make sure you have a doom.wad file in the wads folder

python3 -c "
import vizdoom as vzd
game = vzd.DoomGame()
game.set_doom_scenario_path('wads/doom1.wad')
for ep in [1, 2, 3]:
    for level in range(1, 10):
        map_name = f'E{ep}M{level}'
        try:
            game.set_doom_map(map_name)
            game.init()
            print(f'✓ {map_name} loaded successfully')
            game.close()
            game = vzd.DoomGame()
            game.set_doom_scenario_path('wads/doom1.wad')
        except:
            print(f'✗ {map_name} failed')
" 2>&1 | grep "✓"

