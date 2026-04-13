# Future Work

repo merge and moving ground tools out of doomsat folder.

finalize handoff docs contents

clean up experimental and Thomas branch

recreate gameplay from logs. 

remove svg post-run analysis from Telemtry Writer class so it doesn't happen at runtime because it takes up too much space. Need to update the telemetry doc and TelemetryWriter to not include this.

GA param tweaking: tune GA fitness as Hal instructed, so kills in completion and waypoints normalized in non-completion. Run the GA and observe changes. Then update the ga design doc to reflect. Then update tests/test_compute_fitness.py. Then run pytest before merging.

resume evolve mode. Satellite won't give enough time to run a full evolution so we need a pause/resume feature. Best way to do this is pass the last entry of evolution_history as a CLI arg when we want to resume a session. There's a lot of parts that need to be changed here, such as the plots, plateau counter...

2 pathfinding bugs in bugs/

add more GA outputs from live to the report.py tool and continue experimenting with the live visual tool. This tool was just for our fun, probably not useful to real work since we don't do livestreaming from space, we recreate it on ground. But there's some useful plots in the tool itself that could be added to ga report.

GA runtime improvement by refactoring agent initialization (touches many files be careful). Currently we call init_game for every episode which adds overhead. The reason it exists like this currently is because it's an easy way to reset the level. A better way to do it is have reset functions so we can avoid this overhead. Should see a lot of improvement after this change.

working nav_planner: part1 is fixing the path. Part 2 is adding support for E1M2 mechanics like key-locked doors, and switches. then salvage anything needed from thomas branch and put in reference folder only if necessary, then delete branch.

Update code to support E1M2 mechanics. Test agent on E1M2 after nav_planner updated. See if any other mechanics need to be addressed, such as lifts. What prevents agent from beating level?


## Future ideas

combat improvement: going backwards while shooting to deal with tanky enemies
more exploration system (new states?)

combat ammo waste: if the agent deals no damage after several combat ticks, the enemy is likely behind geometry. A combat blacklist similar to the loot node blacklist would prevent wasted ammo.