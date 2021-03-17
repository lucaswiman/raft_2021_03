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

This bit of code would then run in a dedicated thread.

```
import threading
import queue

...
in_q = queue.Queue()
out_q = queue.Queue()
threading.Thread(target=run_raft, args=[raftserv, in_q, out_q]).start()
...
```

Different elements of the runtime environment would then sequence operations
via the queues.  For example, timer threads could generate time related events,
threads watching the network could deposit incoming messages, etc.

