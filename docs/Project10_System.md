# Project 10 - Systems

Up to this point, you've coded Raft in the form of a model or
simulation.  We've (hopefully) done a lot of testing and debugging.  Now,
it's time to put it into the real world.

The goal here is to build a runtime environment for Raft that uses
real sockets, timers, and threads.  However, in doing this, we don't
want to rewrite all of the code we've developed so far.  Instead, we
want to embed our model into the runtime environment.  The
question, is how to do that?

## Handling Concurrency

One possible way to embed the model into a runtime environment is to write a
function involving thread queues.   Here is the basic shell of the idea:

```
def run_raft(raftserver, in_q, out_q):
    while True:
    	# Get a "request" to do something on the raft server
        request = in_q.get()

	# Process requests on raftserver
        ...

	# Take any responses back to client and put on out_q
	...
```

This bit of code would then run in a dedicated thread and be
the only part of the whole system that interacts with the
Raft code written so far.

```
import threading
import queue

...
in_q = queue.Queue()
out_q = queue.Queue()
threading.Thread(target=run_raft, args=[raftserv, in_q, out_q]).start()
...
```

Different elements of the runtime environment would then sequence
operations via the queues.  For example, timer threads could generate
time related events, threads watching the network could deposit
incoming messages, etc.

## Handling Messaging

To handle messaging, you will need to implement a server that listens
for incoming connections and have threads that are dedicated to receiving
incoming messages.   Incoming messages could be transmitted to Raft via
the queues just described.

For outgoing messages, you might also have threads/queues that are
hooked to the `RaftNetwork` object in some manner.  For example,
after performing any kind of operation on the Raft server, you could
have code that took all of the outbound messages and routed them
to threads responsible for actual delivery.

## Handling Configuration

You will need to config the Raft system in some way.  I'd suggest making
a file `raftconfig.py` that holds information about mapping node numbers
to network addresses as well as other configuration. For example:

```
# raftconfig.py

SERVERS =  {
   0:   ('localhost', 15000),
   1:   ('localhost', 16000),
   2:   ('localhost', 17000),
   3:   ('localhost', 18000),
   4:   ('localhost', 19000)
   }
```

Have your runtime use this to set up servers, manage connections, and
deal with other aspects of the deployment.

## Testing

Testing your code in a networked configuration will become quite a bit more
difficult.  You will need to run each server in a separate process.  This
means running 5 different copies of Python at once--in different terminal
windows.   You may also want to have some way to interact with the server
as it runs.  

Fingers crossed:  If you've done due-diligence on testing and debugging
with Raft up to this point, when you move it to a real network, it will
just "work" as if by magic.


