# Project 6 - Modeling Log Replication

In Project 4, you implemented the basic `append_entries()` operation that's
at the core of Raft. In Project 5, you created a model for the Raft network.
Now, you're going to combine these projects to model log replication.

Warning: This part of the project should not involve a huge amount of
code, but you must integrate a number of pieces together to make it
work.  There are suddenly going to be a lot of moving parts which make
testing and debugging more difficult. Take it slow.

## The Scenario

The goal for this project is to make one server (designated in advance
as the "leader") replicate its log on all of the other servers. It
will do this by sending messages through the Raft network and
processing their replies.  You will be able to append new log entries
onto the leader log and those entries will appear on all of the
followers. The leader will be able to bring any follower up to date if
its log is missing any entries. 

## Some Wishful Thinking

Challenge: How do we structure what we need here?  One way to break
the analysis paralysis is to engage in a bit of "wishful thinking."
We know that Raft involves multiple servers.  We know that that those
servers live as a node on the network and that they have a log.  So, wish
it into existence.

```
class RaftServer:
    def __init__(self, node, log):
        self.node = node
        self.log = log

# Example setup.
net = RaftNetwork(5)    # A network of 5 "nodes"

# Create a few servers on the network
server0 = RaftServer(net.create_node(0), [])
server1 = RaftServer(net.create_node(1), [])
server2 = RaftServer(net.create_node(2), [])
```

There needs to be a way for a leader to add new entries to
its own log.  So, define a method on the class to do it.  This is
a wrapper around the core `append_entries()` function.

```
class RaftServer:
    ...
    def leader_append_entries(self, prev_index, prev_term, entries):
        return append_entries(self.log, prev_index, prev_term, entries)
    ...
```

You also know that the leader must send messages to followers to
make them update their logs.  So, define a method to do that:

```
class RaftServer:
    ...
    def send_append_entries(self):
        # Send an AppendEntries message to all peers to update their logs
        for peers in self.node.peers:
            self.node.send(peer, AppendEntriesMessage(...))
    ...
```

Finally, know that the followers need to receive this message and respond
back to the leader. So, add a few methods for dealing with that.  Each
of these methods operate on a received message of some kind:

```
class RaftServer:
    ...
    def follower_append_entries(self, msg):
        # Process an AppendEntries messages sent by the leader
        success = append_entries(self.log, msg.prev_index, msg.prev_term, msg.entries)
        self.net.send(msg.source, AppendEntriesResponse(...))
    
    def leader_append_entries_response(self, msg):
        # Process an AppendEntriesResponse message sent by a follower
        if msg.success:
             # AppendEntries on msg.source worked!
             ...
        else:
             # AppendEntries on msg.source failed!
```

Again, we're mainly sketching out the shell of what is actually
required to replicate a log.

## Fleshing out Details

Once you've got the shell of what's needed, start to work out more
details.  For example, how are messages received?  How are the
different methods such as `follower_append_entries()` and
`leader_append_entries_response()` actually triggered?

For this, you might have to write a bit of supporting code to drive
things.  For example, maybe a helper function to deliver all pending
messages in the cluster of servers.

```
def process_messages(servers):
    ...
    # Process all pending messages on the Raft servers until none remain
    ...
```

To use this, you might sequence some steps like this:

```
# Create the network
net = RaftNetwork(3)

# Create the servers
server0 = RaftServer(net.create_node(0), [])
server1 = RaftServer(net.create_node(1), [])
server2 = RaftServer(net.create_node(2), [])

# Append a log entry on the leader
server0.leader_append_entries(-1, -1, [ LogEntry(1, 'Hello') ])

# Process messages
process_messages([server0, server1, server2])

# Now verify that the leader replicated the log
assert server0.log == server1.log == server2.log
```

Once you've got basic communication worked out, think about how to
handle failed `AppendEntries` messages. Failures occur when the log
has gaps/holes or is inconsistent in some way.  To fix this, the
leader needs to start working backwards by trying `AppendEntries`
operations with lower indices.  You'll need to add some book-keeping
for this.  Also, testing it is challenging.  You might try
to devise unit tests around some of the figures in the Raft paper
(for example, Figure 6 and 7). 

## Comments

Getting log replication to work might be one of the most difficult
parts of the entire Raft project.  It's not necessarily a lot of code,
but it integrates everything that you've been working on so far.
Testing and debugging is extremely challenging because you've suddenly
got multiple servers and it's hard to wrap your brain around
everything that's happening.  This is where any kind of logging or
debugging features in your earlier work will come in useful.

A critical part of your work here will involve the `process_messages()` function.
Keep in mind that we're still working with a model.  Thus,
to make anything actually happen, you have simulate message delivery.
`process_messages()` will have to pull messages from the simulated network
and route them to appropriate methods on the `RaftServer` class.

You will likely feel that you are at some kind of impasse where
everything is broken or hacked together in some horrible way that
should just be thrown out and rewritten.  This is normal.  Expect that
certain parts might need to be refactored or improved later.

  

 

