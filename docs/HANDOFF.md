# HANDOFF

Hey.

You can start with this doc even if you haven't read the primary readme. Trust.

This doc will tell you the steps I recommend to take to understand this codebase.
It also includes advice about how to contribute and thoughts about why things were done.

## Thesis

The thesis of the project is that in space, cosmic radiation corrupts memory which causes bit flips.
Rather than fixing the spacecraft's conditions with error codes, we want to take advantage of these.
The genetic algorithm mutates parameters that control the agent's gameplay and improves by passing on the better performer.
Tbh, it's still a little fuzzy how this part works, ask the boss for more info.


## Continuing from the previous group

This codebase started January 2026. 
The handoff docs we were given mainly included research into what algorithms work with the spacecraft and Doom.
The algorithms_tree.html was the only thing we thought worth saving.
It will tell you what algorithms in general work well on spacecraft + VizDoom.
```You can take a quick look at it and revisit later if you need context about the broader scope of the project.```
We continued with their conclusion that it would be best to use a state machine for the execution side (agent gameplay).
The downside is that for a surprisingly complex game like DOOM, every mechanic and scenario needs to be addressed.
That is why the agent currently only beats E1M1 (experimental branch beats E1M2).
This is because it's computationally efficient, not expensive.
The alternative would probably be a neural net which we don't know how long it would take to beat all 27 levels.
We did do some experiments with neural net + VizDoom but discontinued because it didn't fit the project scope.
It doesn't fit the thesis because in a neural net, bit flips change weights which just causes destruction, hard to improve this way.
This could be worth more research.

## Failure and adaptation

Our initial approach to the code was to rely heavily on AI without planning beforehand.
This was surprisingly helpful for getting the project off the ground and understanding VizDoom.
We were able to set up the environments fast without having to read documentation.
It gave us a great reference point for how things should work and what capabilities VizDoom has.
We were quickly able to beat E1M1, but found difficulty on levels after because the map layout is so complex.
The codebase quickly grew to an unmaintainable size, and we didn't really understand how anything worked.
Using ai, we put bandaid on top of bandaid until we got stuck.
We got stuck after not making progress for 2 weeks because traversing levels without getting stuck had no real solution yet.
1 month after taking over the project, we restarted with a new approach.


## Prioritize planning before coding
We changed our approach to be more thorough with the system design upfront. 
First was playing through all of DOOM and understanding what kind of complexity the game had.
There are a ton of mechanics that need to be addressed by our execution algorithm.
After realizing this, we started with focusing on beating E1M1, but creating an architecture that could work for all levels.

```Now, just read the readme if you haven't already.```
```Now, acquire the doom.wad``` 
That file is basically just the doom game; there are many ways to get it. Good luck, ask the boss.

```Next, I recommend at some point you play thru at least the first 2 levels to get an understanding of DOOM.```
I used uzdoom.exe; you'll need to find that online. 
You also will need to give it the doom.wad.

```You can also read the doc I made after my full playthrough: game_mechanics.md```
The main takeaway is that levels are very different from each other.
The params that work for one level might crap the bed on the next one.
Thats why the GA evolves params per level. 
If it was for all levels, we'd just end up with one mediocre genome, or just the best genome for the last level.
```Now's a good time to read the genetic_algo_design doc.```



DO NOT BLOW UP THE NODES
#did use ai, would recommend carefully
#claude in terminal