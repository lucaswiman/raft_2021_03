# Project 10 - Systems

Up to this point, you've coded Raft in the form of a model or
simulation.  However, we've done a lot of testing and debugging.  Now,
it's time to put it into the real world.

The goal here is to build a runtime environment for Raft that uses
real sockets, timers, and threads.  However, in doing this, we don't
want to rewrite all of the code we've developed so far.  Instead, we
want to embed our code into this more complex environment.

This might not be as bad as imagine--you already built a sort of runtime
environment for the purposes of testing.  In much earlier parts of the
project, you wrote code involving sockets and messages.
