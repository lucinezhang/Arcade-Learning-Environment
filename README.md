# To do
1. Dataset 
- [x] Record actions in to EDF file 
- [x] Save and reload game
- [x] Game time limits (15 minutes per session then break)
- [x] Validation after each trial, mark and throw away bad data
- [x] Score leaderboard
- [x] Automatically run edf2asc after each trial
- [x] Record random seed to data file
- [ ] A recording schedule for diff. games and subjects
- [ ] Support for composed actions using event detection

2. Imitation
- [x] Make it easier to combine trials(see dataset\_specification\_example.txt)
- [ ] Test regularizer hypothesis (attention as) (what is this???)
- [x] Gaze-centered images as training samples
- [x] Make sure dropout is turned off during evaluation
- [ ] Figure out why GaussianConv model does not work (what is this???)
- [x] Figure out Tau (needs to find gaze & image before easier)
- [x] CNN + past X frames model
- [ ] CNN + positional encoding
- [ ] RNN model

3. Gaze modeling
- [ ] CNN - deconv model
- [ ] CNN - regression model
- [ ] Superior colliculus model

4. RL
- [ ] Make it possible for model to play the game and record scores

5. Psychology
- [x] Ask experts to validate experimental setups
- [ ] Experiment and config class
- [ ] Demographical information survey (ask Sariel)
- [ ] Subject consensus files (ask Sariel) 
- [ ] Organize experimental procedure
- [ ] Practice game for subjects + instructions
- [ ] Write experimental instruction for both experimentor and subjects; note that experimentor should center the screen; experimentor should stay with subjects during experiment 

## Next

[![Build Status](https://travis-ci.org/mgbellemare/Arcade-Learning-Environment.svg?branch=master)](https://travis-ci.org/mgbellemare/Arcade-Learning-Environment)

<img align="right" src="doc/manual/figures/ale.gif" width=50>


### Arcade-Learning-Environment: An Evaluation Platform for General Agents

The Arcade Learning Environment (ALE) -- a platform for AI research.


This is the 0.5 release of the Arcade Learning Environment (ALE), a platform 
designed for AI research. ALE is based on Stella, an Atari 2600 VCS emulator. 
More information and ALE-related publications can be found at

http://www.arcadelearningenvironment.org

We encourage you to use the Arcade Learning Environment in your research. In
return, we would appreciate if you cited ALE in publications that rely on
it (BibTeX entry at the end of this document).

Feedback and suggestions are welcome and may be addressed to any active member 
of the ALE team.

Enjoy,
The ALE team

===============================
Quick start
===============================

Install main dependences:
```
sudo apt-get install libsdl1.2-dev libsdl-gfx1.2-dev libsdl-image1.2-dev cmake
```

Compilation:

```
$ mkdir build && cd build
$ cmake -DUSE_SDL=ON -DUSE_RLGLUE=OFF -DBUILD_EXAMPLES=ON ..
$ make -j 4
```

To install python module:

```
$ pip install .
or
$ pip install --user .
```

Getting the ALE to work on Visual Studio requires a bit of extra wrangling. You may wish to use IslandMan93's [Visual Studio port of the ALE.](https://github.com/Islandman93/Arcade-Learning-Environment)

For more details and installation instructions, see the [website](http://www.arcadelearningenvironment.org) and [manual](doc/manual/manual.pdf). To ask questions and discuss, please join the [ALE-users group](https://groups.google.com/forum/#!forum/arcade-learning-environment).


===============================
List of command-line parameters
===============================

Execute ./ale -help for more details; alternatively, see documentation 
available at http://www.arcadelearningenvironment.org.

```
-random_seed [n] -- sets the random seed; defaults to the current time

-game_controller [fifo|fifo_named] -- specifies how agents interact
  with ALE; see Java agent documentation for details

-config [file] -- specifies a configuration file, from which additional 
  parameters are read

-run_length_encoding [false|true] -- determine whether run-length encoding is
  used to send data over pipes; irrelevant when an internal agent is 
  being used

-max_num_frames_per_episode [n] -- sets the maximum number of frames per
  episode. Once this number is reached, a new episode will start. Currently
  implemented for all agents when using pipes (fifo/fifo_named) 

-max_num_frames [n] -- sets the maximum number of frames (independent of how 
  many episodes are played)
```

=====================================
Citing The Arcade Learning Environment
=====================================

If you use ALE in your research, we ask that you please cite the following.

M. G. Bellemare, Y. Naddaf, J. Veness and M. Bowling. The Arcade Learning Environment: An Evaluation Platform for General Agents, Journal of Artificial Intelligence Research, Volume 47, pages 253-279, 2013.

In BibTeX format:

```
@ARTICLE{bellemare13arcade,
  author = {{Bellemare}, M.~G. and {Naddaf}, Y. and {Veness}, J. and {Bowling}, M.},
  title = {The Arcade Learning Environment: An Evaluation Platform for General Agents},
  journal = {Journal of Artificial Intelligence Research},
  year = "2013",
  month = "jun",
  volume = "47",
  pages = "253--279",
}
```


