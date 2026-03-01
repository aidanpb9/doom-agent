# Doom Game Mechanics Documentation

## Overview
This doc does not include specifics on every single game mechanic. Instead, it is info about the most critical mechanics covering all levels of DOOM that would need to be addressed by an autonomous agent. Not every level uses every mechanic: early levels are simpler. Game was played using UZDoom platform.

**Process:**
Played through the 27 levels of Doom (E1M1 - E3M9). Noted all the important game mechanics that would need to be addressed by an execution algorithm. Had AI organize the notes, then edited and verified the doc by hand. 


## 1. Movement & Navigation

**Basic Movement:**
- Forward, backward, strafe left/right, turn left/right
- Sprinting increases movement speed
- Jump and crouch were not a part of original DOOM, but some version have it
- Jump and crouch not necessary to beat the game
- Sprint + Jump can clear barrels and small obstacles (rarely required, could help when stuck)


**Stuck Recovery:**
- Many map locations can trap the player (corners, narrow passages)
- Agent must detect and escape stuck states

**Environmental Hazards:**
- Lava (damaging floors) deals damage over time (damage rate varies by color/type)
- Radiation suit powerup allows safe lava traversal for limited time
- Sometimes lava crossing is mandatory
- Some lava pits are inescapable (eventual death), others have exits (paths, levers, elevators)
- Crushing ceilings in some areas (Rapid damage)


## 2. Combat

**Weapons:**
- Fist (weapon slot 1) is always available, melee range
- Multiple weapons available with different characteristics such as:
effective ranges,
damage outputs,
ammo types,
max ammo capacities
- No reloading mechanic (continuous fire until ammo depleted)
- Weapon switching takes time (can't instant-switch)
- Better weapons found on the later levels

**Weapon Mechanics:**
- High fire-rate weapons delay/slow enemies
- Rockets cause self-damage based on proximity, but can also propel player upwards

**Enemy Behavior:**
- Enemies strafe (requires aim tracking)
- Some enemies are "invisible" (partially transparent)
- Enemies can drop loot (ammo, health, armor, weapons) upon death
- Different enemy types have different speeds, attack patterns, and health
- Some enemies have projectile attacks, others are melee
- Infighting: enemies can damage each other

**Combat Strategies:**
- Can shoot enemies through windows from safety
- Boss enemy (Cyberdemon) best defeated by circle-strafing
- Cover and line-of-sight management important
- Sound attracts enemies (gunfire draws attention)

**Environmental Combat:**
- Explosive barrels can be shot to deal area damage
- Barrels damage player and enemies based on proximity
- Barrel explosions chain-react to nearby barrels
- Some wall textures can be shot to reveal secrets (extremely rare)

## 3. Resources & Items

**Loot Types:**
- Health packs (various amounts)
- Armor (regular armor and super armor at key locations)
- Ammo (type-specific, with max capacity limits)
- Can't pick up loot beyond max capacity

**Loot Behavior:**
- Loot scattered on ground throughout levels at spawn time
- Loot can be dropped by enemies upon death
- Loot does NOT respawn once collected
- some loot placed across hazards (requires damage to obtain)
- Better loot may be worth tracking by the algorithm while worse loot may not

**Powerups:**
- Radiation suit (lava immunity, temporary)
- Light amplification goggles (better vision)
- Invisibility (partial transparency to enemies)
- Computer area map (reveals automap)
- Invulnerability (temporary god mode)
- Berserk (10x melee damage)

## 4. Doors, Switches, and Progression

**Door Mechanics:**
- Press USE to open/close most doors
- Rapid USE spam toggles doors quickly
- Some doors look identical to walls (must try USE on suspicious walls)
- Some doors require keys (colored key system: red, blue, yellow)
- Keys must be found before accessing locked doors
- Some doors open automatically when approached
- Some doors close after a delay

**Panels:**
- Press USE to activate
- Most panel activations are permanent and beneficial (don't block progress)
- Some panels are temporary/timed (must traverse area quickly after activation)
- Some panels trigger new panels to appear
- Complex puzzles may require multiple panel combinations to open doors
- Some panels are remote (affect areas far from the switch)

**Keys:**
- Three colored keys: Red, Blue, Yellow
- Required to open matching colored doors
- Must be collected before accessing locked areas
- Opening a key-locked door does not consume the key
- There can be multiple key-locked doors of the same type on a level (ex: multiple blue doors)

## 5. Elevators & Platforms

**Elevator Behavior:**
- Usually does not require USE to activate, just stand on it
- May take several seconds to activate (requires patience)
- Sometimes required to obtain keys or reach areas
- Platform-waiting may be necessary (stand on platform while it rises to reach levers)
- Some platforms are triggered by switches, not USE
- Some are one-time use, others can be re-triggered

## 6. Teleporters

**Teleporter Types:**
- Standard teleporters
- One-way teleporters (can't return same way)
- Conditional teleporters (behavior changes based on game state)
- Some teleporters are triggered by entering area, others by switches
- Teleporter destinations not usually obvious

## 7. Secrets

**Secret Areas:**
- Secret rooms/paths can be found within levels
- Secret rooms contain valuable loot
- Secret levels exist (E1M9, E2M9, E3M9 are technically secret levels)
- Secret walls open when USE is pressed
- Secret elevators hidden in corners
- Some secrets open automatically when approached
- Secrets often indicated by texture misalignment or suspicious geometry
- Not required for level completion

**Secret Mechanisms:**
- Hidden switches
- Shootable walls (extremely rare)
- Rocket-jump techniques to reach hidden areas

## 8. Level Structure & Objectives

**Level Goals:**

- Find exit and press USE on exit panel
- Fake exits signs exist (the room behind is not the exit, rare)
- Some exits are locked until objectives completed (find all keys, hit all switches)

**Level Progression:**
- Player stats (health, ammo, armor, weapons) carry over to next level
- Death restarts level from entry point (no penalty, full reset)

**Spatial Complexity:**
- Multi-elevation areas (enemies above/below player)
- Vertical differences affect combat and navigation
- Secret windows can be jumped out of (may need rocket propulsion to return)
- Some areas accessible only from specific directions
- One-way drops exist (can drop down but can't climb back up)

**Dynamic Environment:**
- Entering certain locations unlocks new paths (without switch activation)
- Map geometry changes based on switches
- State-dependent paths (some areas only accessible after certain actions)
- Traps can trigger when entering areas (enemies released, crushing ceilings)