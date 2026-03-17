# Telemetry Tiers (DOOMSat v2)

This folder contains four outputs used by DoomSat telemetry:

- Tier 0: `on-demand.jsonl`
- Tier 1: `level-summary.json`
- Tier 2: `action-stream.csv`
- TLP: `latest.txt` (Two-Line-Plus)

Files are created by `TelemetryWriter.start_episode()` and finalized at episode end.

## 1) Tier 0 — `on-demand.jsonl`

**File:** `telemetry/tier0/on-demand.jsonl`

**Purpose:**

- Per-step/per-frame telemetry stream (high-frequency events).
- Written in JSONL format (one JSON object per line).
- Intended for fine-grained replay / debugging / health and state analysis.

**Exact field semantics (implementation-accurate):**

- Envelope
  - `type`: constant `"tier0_telemetry"`
  - `schema`: constant `"v2"`
  - `unix_time`: current Unix timestamp in seconds (integer)
  - `run_id`: run identifier (u32), generated at writer init
  - `episode_id`: episode code (u16), derived from `level_id`
  - `algo_id`: algorithm identifier string (lowercased)
  - `git`: short git hash, or `"unknown"` if unavailable
  - `rng_seed`: episode RNG seed (u32)

- spacecraft
  - `state`: spacecraft state string in `{safe,idle,comms,nominal,safety1,safety2}`; defaults to `nominal` if invalid
  - `state_change_unix_ms`: Unix ms when spacecraft state last changed
  - `vbat_v`: battery voltage in volts (currently placeholder `0.0`)
  - `ibat_a`: battery current in amps (currently placeholder `0.0`)
  - `soc_pct`: battery state-of-charge percent (u8); from `psutil` battery if available, else `100`
  - `board_temp_c`: board temperature °C (from first `psutil` temp sensor if available)
  - `cpu_temp_c`: CPU temperature °C (from first `psutil` temp sensor if available)
  - `seu_count`: single-event upset count (u16, currently `0`)
  - `sed_count`: single-event disruption count (u16, currently `0`)
  - `heap_free_b`: free heap bytes (u32, currently `0`)
  - `stack_hwm_b`: stack high-water-mark bytes (u32, currently `0`)
  - `rssi_dbm`: link RSSI in dBm (i8, currently constant `-92`)
  - `err_rate_ppm`: link error rate in ppm (u16, currently `0`)

- vizdoom
  - `tick`: game tick (u32)
  - `frame_id`: frame counter (u32)
  - `scene_id`: scene code (u16), derived from `level_id`
  - `action`: encoded action bitmask (u16)
    - bit0 `ATTACK`
    - bit1 `USE`
    - bit2 `MOVE_FORWARD`
    - bit3 `MOVE_BACKWARD`
    - bit4 `TURN_LEFT`
    - bit5 `TURN_RIGHT`
    - bit6 `STRAFE_LEFT`
    - bit7 `STRAFE_RIGHT`
    - bit8 `SPEED` (reserved in current encoder; not set)
    - bit9 `STRAFE` mode (set when bit6 or bit7 is set)
  - `step_ms`: step wall-clock duration rounded to ms (u16)
  - `timeout_active`: whether timeout logic is active this step (bool)
  - `timeout_reason`: normalized reason string in `{none,wall_clock,max_steps,hang_no_movement,player_dead,state_none,error}`
    - `"error:*"` is normalized to `"error"`
    - unknown values are normalized to `"none"`
  - `timeout_count`: cumulative timeout count (u16)
  - `cpu_ms`: CPU time for step in ms (u16)
  - `mem_b`: process resident memory bytes (u32)
  - `state_hash`: u32 CRC32C over `"tick|frame_id|scene_id|health|ammo|kills|pos_x|pos_y|angle"`

- player
  - `hp`: health (u8, rounded)
  - `armor`: armor (u8, currently hardcoded `0`)
  - `keys.red/blue/yellow`: bool flags inferred from labels containing key/card/skull + color name
  - `secrets_found`: secrets count (u8, currently hardcoded `0`)
  - `ammo.bullets`: ammo count (u16, rounded from `state_info["ammo"]`)
  - `ammo.shells/rockets/cells`: currently hardcoded `0` (u16)
  - `combat.damage_in`: `max(0, last_health - health)`, rounded to u16
  - `combat.damage_out`: `100 * max(0, kills - last_kills)`, rounded to u16
  - `combat.source`: first label object name if `damage_in > 0`, else `"none"` (or `"unknown"` if no label name)
  - `combat.target`: first label object name if `damage_out > 0`, else `"none"` (or `"unknown"` if no label name)

- perf
  - `fps`: `1000 / frame_ms` (`0` if `frame_ms <= 0`)
  - `frame_ms`: step wall-clock duration in ms (float)
  - `cpu_pct`: `clamp(100 * cpu_ms / frame_ms, 0..100)`, `0` if `frame_ms <= 0`
  - `rss_mb`: process resident memory in MB (float)
  - `gc_events`: cumulative Python GC collections since episode start (u16 delta)

- outcome and integrity
  - `outcome`: caller-provided status string, lowercased (default `"alive"`)
  - `crc32c`: 8-hex lowercase CRC32C of canonical JSON serialization (sorted keys, compact separators), computed with `crc32c` field excluded then inserted

**Notes:**

- Written from `record_step()` each simulation step.
- Action bits are encoded through `encode_action_bitmask()`.
- This is the primary per-step log.

## 2) Tier 1 — `level-summary.json`

**File:** `telemetry/tier1/level-summary.json`

**Purpose:**

- Episode-level summary generated once at episode completion.
- Represents high-level outcome and mission-level metrics.

**Exact field semantics (implementation-accurate):**

- Envelope
  - `type`: constant `"level_summary"`
  - `schema`: constant `"v2"`
  - `unix_time`: current Unix timestamp in seconds (integer)
  - `run_id`: run identifier (u32), generated at writer init
  - `episode_id`: episode code (u16), derived from `level_id`
  - `algo_id`: algorithm identifier string (lowercased)
  - `git`: short git hash, or `"unknown"` if unavailable
  - `rng_seed`: episode RNG seed (u32)

- episode
  - `level_id`: uppercase level string provided to `start_episode()`
  - `result`: `"win"` iff `end_reason == "exit"`, otherwise `"loss"`
  - `duration_s`: non-negative float from `finalize_episode(episode_time_s)`
  - `hp_end`: final hp (u8), from last Tier 0 packet `player.hp`, else `0` if no steps emitted
  - `armor_end`: final armor (u8), from last Tier 0 packet `player.armor` (currently always `0`)
  - `keys.red/blue/yellow`: final key flags from last Tier 0 packet, else all `false`
  - `secrets_found`: u8, currently hardcoded `0`

- damage
  - `taken`: cumulative integer damage in (u32), sum of per-step `max(0, last_health - health)`
  - `dealt_total`: cumulative integer damage out (u32), sum of per-step `100 * max(0, kills_delta)`
  - `dealt_by_enemy`: currently empty object `{}`

- resources
  - `ammo_used.bullets`: `max(0, round(ammo_start - ammo_end))` as u16
    - `ammo_start` is captured when first emitted step has `last_ammo == 0` and no Tier 2 rows yet
    - `ammo_end` is latest observed ammo from `record_step()`
  - `ammo_used.shells/rockets/cells`: currently hardcoded `0` (u16)
  - `medkits_used`: currently hardcoded `0` (u8)
  - `armor_picked`: currently hardcoded `0` (u16)

- efficiency
  - `damage_per_ammo`: `dealt_total / ammo_used.bullets`, or `0.0` if bullets used == `0`
  - `targeting_pct`: currently hardcoded `0.0`
  - `overkill_pct`: currently hardcoded `0.0`

- navigation
  - `path_len_m`: cumulative 2D path length from per-step position deltas `sqrt(dx^2 + dy^2)`
  - `backtrack_pct`: currently hardcoded `0.0`
  - `stuck_events`: `nav_stuck_events` argument clamped to u8
  - `recoveries`: `nav_recoveries` argument clamped to u8

- faults
  - `ecc_corrected`: currently hardcoded `0` (u16)
  - `bitflips_injected`: currently hardcoded `0` (u16)
  - `watchdog_resets`: currently hardcoded `0` (u16)
  - `divergence_events`: currently hardcoded `0` (u16)

- integrity
  - `crc32c`: 8-hex lowercase CRC32C over canonical JSON serialization (sorted keys, compact separators), computed with `crc32c` field excluded then inserted

**Notes:**

- Written in `finalize_episode()`.
- This is the concise episode scorecard.

## 3) Tier 2 — `action-stream.csv`

**File:** `telemetry/tier2/action-stream.csv`

**Purpose:**

- Compact per-step action stream for lightweight replay/post-processing.
- CSV header + one row per step.

**Header:**

`t,tick,scene,frame,action,seed,state,cpu_ms`

**Field meaning:**

- `t`: Unix timestamp in ms at row creation (`_now_unix_ms`)
- `tick`: game tick (u32)
- `scene`: scene id (u16), derived from `level_id` at episode start
- `frame`: frame counter (u32)
- `action`: encoded action bitmask as lowercase 4-hex with `0x` prefix (e.g., `0x0014`)
- `seed`: run RNG seed (u32)
- `state`: 8-hex lowercase state hash from Tier 0 `vizdoom.state_hash`
- `cpu_ms`: per-step CPU time in ms (u16)

**Row creation behavior:**

- Created only when `record_step(..., emit_action_row=True)`
- Written immediately to CSV and flushed per-row
- In-memory copy is retained in `self._tier2_rows` for TLP emission

**Notes:**

- Rows are written whenever `emit_action_row=True` in `record_step()`.
- Tier 2 rows are also embedded into the TLP output.

## 4) TLP — `latest.txt`

**File:** `telemetry/tlp/latest.txt`

**Purpose:**

- Legacy compact textual telemetry format that combines:
  - a fixed 2-line TLE header
  - one spacecraft/platform status line
  - one summary status/timing line
  - one row per Tier 2 action-stream entry

**Exact line format (implementation-accurate):**

- Line 1: fixed default TLE line 1 constant
- Line 2: fixed default TLE line 2 constant

- Line 3 format:
  - `3 unix_ms state_code vbat ibat soc board_temp_tenths cpu_temp_tenths seu sed heap stack rssi err_rate clock_skew_ppm`
  - `unix_ms`: current Unix ms at TLP generation
  - `state_code`: spacecraft state code map
    - `safe=0`, `idle=1`, `comms=2`, `nominal=3`, `safety1=4`, `safety2=5`
  - `vbat`, `ibat`: taken from last Tier 0 spacecraft values (currently `0.00`, `0.00`)
  - `soc`: last Tier 0 `spacecraft.soc_pct` (u8)
  - `board_temp_tenths`/`cpu_temp_tenths`: last Tier 0 temps multiplied by 10 and rounded to int
  - `seu`/`sed`/`heap`/`stack`/`rssi`/`err_rate`: from last Tier 0 spacecraft payload
  - `clock_skew_ppm`: currently `0`

- Line 4 format:
  - `4 tick scene frame action_hex rng_seed state_hash_hex cpu_ms mem_b timeout_active timeout_reason_code timeout_count`
  - If Tier 2 rows exist, values are sourced from the latest Tier 2 row where applicable
  - Otherwise fallback values are sourced from latest Tier 0 `vizdoom` payload
  - `timeout_active`: `1` if true else `0`
  - `timeout_reason_code` mapping:
    - `none=0`, `wall_clock=1`, `max_steps=2`, `hang_no_movement=3`, `player_dead=4`, `state_none=5`, `error=6`
  - `timeout_count`: cumulative timeout count (u16)

- Lines 5+:
  - One line per stored Tier 2 row in order of emission
  - format: `line_no t tick scene frame action_hex seed state cpu_ms`
  - `line_no` starts at `5` and increments by `1`
  - `action_hex` in these rows is written without `0x` prefix

**Notes:**

- Produced by `_write_tlp()` during `finalize_episode()`.
- Useful for constrained parsers and quick line-based ingestion.

## Output filename mapping used by this codebase

- Tier 0 -> `telemetry/tier0/on-demand.jsonl`
- Tier 1 -> `telemetry/tier1/level-summary.json`
- Tier 2 -> `telemetry/tier2/action-stream.csv`
- TLP -> `telemetry/tlp/latest.txt`
