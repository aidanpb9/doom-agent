## Sprint 3/30-4/15 (All these have a task card in kanban)

- Showcase + poster + team pic (all)

FSW integration User Story 3: 
- (Thomas) recreate gameplay from logs. 
- (FSW) design and document how FSW runs DOOM and where it lives in repo.
- (Aidan) Telemetry: redesign telemetry for minimum info, don't need all tiers, update the docs using that design, move svg to report.py so it doesn't happen at runtime, and change the Telemtry Writer class to reflect the new design 
- (Aidan + Blake) Repo merge. 
- (All)Test full process.

### Thomas
(Thomas) delete experimental branch, not the Thomas branch yet. That comes after nav_planner working for E1M2

(Thomas) GA param tweaking: tune GA fitness as Hal instructed, so kills in completion and waypoints normalized in non-completion. Run the GA and observe changes. Then update the ga design doc to reflect. Then update tests/test_compute_fitness.py. Then run pytest after before pr.

(Thomas) working nav_planner: part1 is fixing the path. Part 2 is adding support for E1M2 mechanics like key-locked doors, and switches. then salvage anything needed from thomas branch and put in reference folder only if necessary, then delete branch.

### Aidan
(Aidan) update GA parallelism doc about hardware constraints 

(Aidan) change GA plots to sigma not stddev, and move legend from middle 

(Aidan) Handoff doc with contribution process 

(Aidan) move relevant onedrive stuff to github 

## Backlog

Update code to support E1M2 mechanics. Test agent on E1M2 after nav_planner updated. See if any other mechanics need to be addressed, such as lifts. What prevents agent from beating level?

add more GA outputs from live to the report.py tool

continue experimenting with the live visual tool

(Thomas) handoff. Blocker: Aidan finish first.

2 pathfinding bugs in bugs/

GA runtime improvement by refactoring agent initialization (touches many files be careful). Currently we call init_game for every episode which adds overhead. The reason it exists like this currently is because it's an easy way to reset the level. A better way to do it is have reset functions so we can avoid this overhead. Should see a lot of improvement after this change.

## Future ideas

combat improvement
combat waste
more exploration system (new states?)
