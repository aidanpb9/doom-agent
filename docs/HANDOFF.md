# HANDOFF

Hey.

This doc will tell you the steps I recommend to take to understand this codebase.
It should take you a while to make it thru this guide, don't rush. Perhaps read it twice, once skimming the docs mentioned and again going more in depth so you understand what you're looking at.

It also includes advice about how to contribute and thoughts about why things were done the way they were. 

Our team had a Doom side and a FSW side. This Doom folder/repo includes everything you need to know about the Doom code and a little about its integration with FSW, but not the FSW stuff itself. 

I didn't include anything that would be more of a nuisance to read like our written reports and presentations which were mostly just yap and specific to Auburn. So if its in this doom folder/repo it's safe to assume it's important and has some use worth noting. If there's FSW docs they're not here.


## Thesis

The thesis of the project is that in space, cosmic radiation corrupts memory which causes bit flips.
Rather than fixing the spacecraft's conditions with error codes, we want to take advantage of these.
The genetic algorithm mutates parameters that control the agent's gameplay and improves by passing on the better performer.

Right now we completed ground testing for E1M1 (first doom level). When it gets deployed in space there will need to be changes and the other docs should help with that. Also, not everything here is perfect, we worked very quickly so feel free to question things and discuss with boss.


## Continuing from the previous group

This codebase started January 2026.
The handoff docs we were given mainly included research into what algorithms work with the spacecraft and Doom.
The algorithms_tree.html was the only thing we thought worth saving.
It will tell you what algorithms in general work well on spacecraft + VizDoom. It's pretty cool.
```You can take a quick look at it and revisit later if you need context about the broader scope of the project.```

We continued with their conclusion that it would be best to use a state machine for the execution side (agent gameplay).
The downside is that for a surprisingly complex game like DOOM, every mechanic and scenario needs to be addressed.
That is why the agent currently only beats E1M1 (experimental branch beats E1M2).
A state machine is a lot more computationally efficient and inexpensive than a neural net, important to consider on a satellite.
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
The codebase quickly grew to an unmaintainable size, and we didn't really understand all the moving parts.
We ended up putting bandaid on top of bandaid until we got stuck.
The main issue was traversing levels without getting stuck on objects.
1 month after taking over the project, we restarted with a new approach.
We changed our approach to be more thorough with the system design upfront.
First was playing through all of DOOM and understanding what kind of complexity the game had.
There are a ton of mechanics that need to be addressed by our execution algorithm.
After realizing this, we started with focusing on beating E1M1, but creating an architecture that could work for all levels.


## Learning tech stack and codebase features

Before we get into the project itself, I'll tell you the tools we used.
If you're not familiar with any of it, not a big deal, most of it is easy to pick up.

All Doom code is python.
VSCode was our IDE of choice.
VizDoom is imported to make coding the agent easier.
We use git and github for version control.

For project management, we used OneDrive to store team artifacts like timesheets, reports, videos.
We used Agile Methodology.
We drafted user stories and their associated tasks in a word doc.
Then we transferred those tasks to a Kanban board in GitHub using GitHub Issues.

There is a pytest test suite with unit tests and one integration test file in tests/.
There is a ruff linter which enforces code style.
A CI pipeline runs on every push to a selected branch (easy to configure, it's just the .github/workflows/ci.yaml)
It runs the unit tests and the linter.
The CI does not run the integration tests because the .wad is not legally shareable and those integration tests are runtime tests.
Docker is set up with the top-level Dockerfile and .dockerignore files, but don't worry about it, it only supports headless run mode.

There are other things that are standard but just in case:
The .gitignore is for not committing unwated files.
The pyproject.toml is for requirements.
The pycache folders are generated at runtime just ignore them.
There's some other files and folders generated by these tools that can be ignored too.


## Onboarding

Your first week or two will be setting up the Agile workflow, watching onboarding videos, and making tasks to fill the KanBan board.
To get the most out of these tasks, they should actually reflect how you will do the work.
This means you need an understanding of what you are doing.
That first sprint was rough for us because we made tasks without any idea of what we'd actually be doing.
Before you try to make tasks, advocate for understanding the codebase first.
We've left some tasks in docs/future_work.md.

## Overview of our project and Doom

```download presentation.pdf. It's great overview of the project and the things you'll find here.```
A lot of the pictures came from docs/ which you'll see later, as well as outputs the code produces.

```Now, acquire the doom.wad```
That file is basically just the doom game; there are many ways to get it. Good luck, ask the boss. Make sure to put it where the readme specifies.

```Now, read the readme if you haven't already and run the different modes so you can see the inputs and outputs. The GA will take a while so just cancel after a few generations. Note the output/ structure.```


```At some point play thru a few levels yourself to get an understanding of DOOM, and think about all the mechanics you'd need to address with code.```
I used uzdoom.exe; you'll need to find that online.
You also will need to give it the doom.wad.

```You might find the doc I made after my full playthrough helpful: game_mechanics.md```
The main takeaway is that levels are very different from each other.
The params that work for one level might crap the bed on the next one.
Thats why the GA evolves params per level.
If it was for all levels, we'd just end up with one mediocre genome, or just the best genome for the last level.

## Genetic Algorithm

```Now's a good time to read the genetic_algo_design doc.```
If there's figures view them on github so they render right.
So the GA is basically a wrapper around the code in core/.

```Now read the ga_parallelism doc (just skim for the first time).```
It explains multiprocessing in python and how we've used it for the GA.
Basically we just run the elite and challenger on 2 different cores. 

```Take a gander at the code in ga/. Reading top level docstrings, classes names, and function names is enough for now.```

## Execution Algorithm

You should have a good idea of the GA's role in the experiment, so we can move onto the core/, known as the "execution algorithm".
This is the main part of the code that controls the agent's gameplay.
If you want the agent to beat more levels or behave differently, this is where to go.

```Now read the state_machine_design.```
It's easy to understand without knowing the rest of the system yet.

```Then read the system_design to see how all the parts work together.```

```Then read class_reference.```

```Then check out out any code you're curious about. Go into all the files and just read the class and function names.```


## Config

The .cfg is for the vizdoom engine. The c++ vizdoom engine provides utilities that make our lives really easy. For example, instead of trying to figure out how we know if something's on the screen using like pixels or internal game code, vizdoom does that for us.
```Now read platform_evaluation in-depth, won't take long.```

In constants, there's fixed constants and GA constants. Fixed constants are not worth tuning, like max_combat_range isn't a meaningful change because there is only one max range, and turning it down is just a bad strategy. Remember that what is there is all used in some way.
```Now skim config/ focusing on the comments.```


## Maps Folder

Maps is where the pre-processing happens. 
The images are helpful for seeing the map.
The json is what is loaded into the graph at runtime start.
This is where the WAD is stored too.
```Look at the stuff in maps. Don't read the tools code though, not worth understanding.```


## Our process with AI

We used AI heavily throughout this project because we had to move fast, but double checked everything.
We did have permission from the boss of course: "Vibecode away".
You should now know not to just vibecode.
This means almost everything has a human stamp of approval.

Since we designed so much of the system first, the docs were an effective guideline for the ai and we updated the docs frequently as we developed.
It proved effective in finding all the places that a change needed to occur when changing one aspect, like if updating a path.
It also proved effective to build larger tasks in layers, so starting with research and docs, then an outline, then skeleton code, then implementation.

Everything in tests/ was ai-generated, but done so carefully layer by layer. 
Tests pass and were all reviewed for correctness.

The tools and plots were ai-generated, I would not recommend trying to understand it in-depth.
Just use the visuals they output to be the judge of if it worked, and have ai do it.

Everything else had some AI-assistance, but every decision was thought through by a person and can be trusted.
Or perhaps trusted less because a human made it.

I used Claude pro for $20/month and used the built in claude code agent in VSCode.
Use it for writing tests, drafting docs, and understanding the code because it's great at that.
Don't use it to make architectural decisions without understanding it yourself.
Do not vibecode, you need to think through how something should work first and plan it before you code it.

## Contributing

The modular architecture supports the addition of mechanics necessary for beating later levels, it just needs to be added.
There's some tasks left in the future_works doc you can start with. They're not all necessary to do.
Here's an example of how I would add some mechanics:

Starting on E1M2 there's key-locked doors which requires picking up a specific color keycard to open that door.
It's always red, blue, and yellow; they have special wad numbers too like how the doors and exits have special numbers.
I'd have the agent traverse to the exit normally.
When it runs into a key-locked door, figure out how it gets feedback to know the door is locked and requires a specific colored key.
Then set the goal node as the key. 
That would require knowing where the keys are and loading it and a node path to it into the graph from the json.
That means the navigation_planner tool needs to create multiple routes.
Right now it works by placing nodes in the center of geometries, trying to connect paths with A*, and if there's a blocking segment then create more nodes to try to find another route. 
It does so from the level start to level finish.
But to know how to get to a key you might want to run it again from level start to the key for all keys in map.
This will be tricky because then there's multiple paths instead of just one.

Also in E1M2 is platforms. One idea to deal with it is if the nav_planner knows where platforms are, we can check if agent is within distance of the platform and if so then stop moving for a few seconds. Would have to play through the game to test if that approach would actually work and if it would be worth making a GA param like platform_time_waiting.

After doing research on my own and writing up these ideas, I'd put it into the terminal AI and ask about pros and cons, any problems this might encounter, better options, and how this feature would be built into the existing code. This is the part you should really spend time thinking about. Then run the agent in window mode and see how it does. Then update any relevant docs once the feature is made.

## Random helpful stuff
Linear scan of the node graph was used for finding nodes. That means you need to keep the node count under control.
We want to limit the agent's initial info when it starts the level so we can see it learning throughout the GA.
But some things are too hard to make work and you just need to have the agent deal with it.
For example, on one level you have to stand on a platform for many seconds as it raises so you can hit a switch.
That requires a creative solution because it's rare and wouldn't work well with the stuck state.
Since you're collaborating, make feature branches and review each other's pull requests. Nobody should own the main branch.
The last 9 levels have teleporters lol.

We also gave the agent the path it needs to follow rather than having it explore the map itself.
This is because the latter scenario is 10x as difficult to implement.
It would be like implementing a SLAM system, the same kind of thing that self driving cars use to identify where they are.
Thats at least a full semester's worth of work; it would add complexity that is cool but unneeded.
Adding this would be probably be like ripping a pillar out of a building, since a lot of the architeture was designed on top of the navigation.
You could still reuse a lot of the core/execution.

## FSW integration

Our team had a FSW side that handled the flight software in F' (F Prime), which is NASA's open source flight software framework. 
The Doom code is the payload.
FSW tells it when to run and receives the gameplay logs back, then it should downlink that along with spacecraft health to Earth.
Then those gameplay logs will be used to recreate the gameplay and livestreamed to youtube so people can watch "Space Plays Doom."
You'll need to make a new set of tools for recreating that gameplay.
You'll also have to test the replay determinism to ensure what's being recreated is based on the original (think seeds and floating point errors).

What FSW has is the operational modes framework and ground data system. The two sides have not been fully wired together yet, so a full ground integration test is the next group's first major milestone. This is listed in future_work.md.

What that test looks like: FSW sends an F' command that triggers a Doom episode, the episode runs and writes telemetry, that telemetry gets downlinked through the ground data system, and gameplay is recreated on the ground. None of those handoff points between the two sides have been tested end to end. 
Then you'll want to test the GA and figure out how the GA will potentially pause if the satellite switches modes.

The Doom side is ready for FSW integration for ground testing as far as one episode goes. 
But the ultimate goal is to have it beating as many levels as possible before launch.
Do not expect to beat all 27 levels. You should realistically be able to beat a few more levels successfully in the time of one semester.
Also I don't know what direction the boss will have you working in.
You may not be trying to beat any more levels and instead just getting it ready for hardware integration and space deployment.

## Good Luck Have Fun