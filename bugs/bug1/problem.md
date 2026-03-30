Where observed: in demo video from 3/30 presentation. Telem files attached.

The bug: a loot node is removed from the graph mid-recovery without the agent reaching or picking up the loot. has_loot_node() then returns False and RECOVER silently drops to TRAVERSE, leaving the agent with unaddressed low armor. The cause is likely the loot node cooldown or cleanup logic triggering incorrectly — the node is close enough to some position threshold or timer that it gets pruned even though the item is still on the floor.

To diagnose: add a print/log line everywhere a loot node is removed in path_tracker.py — include the node name, position, and the reason for removal. Run the same episode and you'll see exactly which code path removed the armor node on tick 2624.

The fix depends on the cause:

If _cleanup_incidental_node() removed it — the proximity check fired even though armor didn't increase. The fix is to only remove a loot node when the corresponding stat actually changed, not just proximity.
If the cooldown timer expired — the node was added, timed out before the agent arrived, and got pruned. The fix is to either extend LOOT_NODE_COOLDOWN or reset the cooldown when the node is the active recovery target.
If set_goal_by_type couldn't find a path to it — A* failed silently and returned no goal. The fix is to blacklist unreachable nodes rather than just ignoring them.
The logging step needs to happen first before committing to a fix — you don't want to patch the wrong code path.