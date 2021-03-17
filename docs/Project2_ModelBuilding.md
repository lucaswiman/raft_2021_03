# Project 2 - Model Building

If one looks at almost any distributed system, you quickly realize that understanding the
operation of the system is quite complex.  There are multiple servers.
There are messages.  There are many ways that the system can
fail. Testing is quite difficult--especially if real-world networking
and deployment issues enter the picture.

One way to tame this complexity is to first implement some kind of
model or simulation that removes system elements.   However, how do you do that?

In the previous project, you implemented controller code for a traffic
light.  That code had to interact with various devices via UDP socket
messages.  It might have also involved threads, timers, and other
programming aspects.

Your task in this project is as follows: Implement the traffic light
control logic in a manner that is completely independent of I/O and
runtime elements.  This means no sockets, no threads, no timers, or
any other system component.  The final control logic should be
something that embodies the operation of a traffic light, but be
runable, debuggable, and testable on its own.

In some sense, this project is an exercise in abstraction.   Are
there ways that you can decouple logic from control?   Are there
programming techniques from object-oriented or functional programming
that can help?

