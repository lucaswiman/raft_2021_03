# Project 9 - Timing 

In this project, we're going to extend Raft to incorporate
elements of time-keeping.   Again, we're still working
with the model/simulation.

## Election Timeouts

Each Raft server expects to receive an AppendEntries message from
the leader on a regular interval.  If nothing has been heard within
a certain timeout period, the server calls an election.

Extend your `RaftServer` class with logic that implements this.

```
class RaftServer:
    def __init__(self, ...):
        ...
	self.heard_from_leader = False
	...

    def follower_append_entries(self, msg):
        ...
	self.heard_from_leader = True
	...
	
    def election_timeout(self):
        if not self.heard_from_leader:
	    self.become_candidate()
	self.heard_from_leader = False
```

Assume that the `election_timeout()` method is something that
would be triggered periodically (mechanism currently unknown).
However, when triggered, it would check to see if we've heard
from the leader since the last timeout.  If not, the server
decides to call an election.

To test this, create a collection of servers all as followers.
Then, have one of them timeout.

```
# Create the network
net = RaftNetwork(3)

# Create the servers (all followers by default)
server0 = RaftServer(net.create_node(0), [])
server1 = RaftServer(net.create_node(1), [])
server2 = RaftServer(net.create_node(2), [])

# Election timeout should promote a server to candidate
server0.election_timeout()
assert server0.role == 'CANDIDATE'

# After exchanging various messages related to election,
# server should be leader.
process_messages([server0, server1, server2])
assert server0.role == 'LEADER'

# Have the leader send empty append entries to all followers
server0.send_append_entries()

# Assert that followers won't call an election (heard from leader)
server1.election_timeout()
server2.election_timeout()
assert server1.role == server2.role == 'FOLLOWER'
```

At some point, the election timeout will be hooked up to an
actual timer.  However, for now, simply leave the `election_timeout()`
method as the mechanism for issuing the timeout.

## Leader Heartbeats

The Raft leader sends a "heartbeat" message on a periodic timer. The
heartbeat is actually just the regular `AppendEntries` message.  So,
whatever method you were using to send this message during your
development of log replication is used to send the heartbeat as well.

However, there are some tricky timing interactions concerning the client
that must be addressed.

First, clients need to be able to append new entries onto the leader
log.  Some of this was already addressed in Project 7. However, how
does this interact with leader heartbeats?  One sensible approach is
for client appends to be added to the leader log, but for them to
generate no actual `AppendEntries` messages.  For example:

```
class RaftServer:
    ...
    def client_append_entry(self, item):
        entry = LogEntry(self.current_term, item)
	...
        append_entries(self.log, prev_index, prev_term, [ entry ])
	return    # Do nothing else
    ...
```
The actual `AppendEntries` communication to followers would be
handled in a separate step that only takes place in connection
with the heartbeat.

```
class RaftServer:
    ...
    def leader_heartbeat(self):
        # Send AppendEntries to all followers
	self.send_all_append_entries()
	...
```

As an example, consider a heavily loaded server with a lot of clients.
If 100s of requests were made quickly, those requests would basically
be queued up on the leader.  When it got the heartbeat timer, it would then
send all new requests at once to the followers in a single
`AppendEntries` message.  The main goal is to reduce the number of
messages sent to followers.  This approach also limits the possibility
of overlapping `AppendEntries` messages.

## Are you really the leader?

Each server has a role attribute that indicates that if it's the leader
or not.   However, is this actually enough to establish leadership in
the face of network partitions?   That is, can a client just look at this
and know they're interacting with a valid leader?  Not really.

To be absolutely certain, the only way to determine leadership is if
a) a server says its the leader and b) that server has successfully
received a quorum of responses from its followers since you asked
if it was the leader?

Part (b) is quite subtle, but here's the gist of it.  If you're a
client, you walk up to a server that claims to be the leader (based on
its current role setting).  However, not quite believing it, you
decide to stand there and wait.  You will watch to see if the leader
actually receives a quorum of responses from its heartbeat message (in
the current term).  If so, you at least know that the server was the
leader when you first contacted it.

Your challenge is to implement some kind of API for determining
(with some certainty) that a server is currently the active
leader.   Perhaps it involves a callback function:

```
class RaftServer:
    ...
    def is_leader(self, callback):
        ...

```

This would execute `callback(True)` or `callback(False)` if
the given server is the leader or not.  It's understood that
this determination might be delayed until the server can establish
that it's heard from a quorum of followers.



