# pyeep

Collection of Python audio-related code coming out of learning experiments.

It contains:

* A waveform audio player
* An audio pattern generator with simple waveform synth
* A JACK midi events player

## Getting started

1. Run `./play`
2. You should see at least a "Manual" input, a "Default" scene, and a "Null" output
3. Assign group 1 to the "Null" output, so it matches the output group of the
   "Default" scene
4. Clicking "Pulse" on the manual input should activate the "Null" output
