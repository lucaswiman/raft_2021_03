# Project 8 - Modeling Raft Leader Election

In this project, we work to implement the Raft leader election and
logic for servers switching between follower/candidate/leader roles.
We continue to work with the Raft model developed in Projects 4-7.

As we don't have an actual "runtime" as of yet, the focus of
this project is on role transitions.    Give your `RaftServer`
class three methods and a few extra attributes:

```
class RaftServer:
    def __init__(self, log, node):
        ...
	self.role = 'FOLLOWER'
        self.current_term = 1
    ...
    def become_leader(self):
        ...

    def become_follower(self):
        ...

    def become_candidate(self):
        ...
```

The goal is to implement these three methods and all of the actions
that take place when a server changes its role.   Roughly, the
following things need to happen:

1. A server that becomes a "follower" becomes passive. It simply
sets its role to follower and initiates no actions at all.

2. A server that becomes a "candidate" increments its term number
and sends out a RequestVote message to all of its peers. It 
listens for incoming RequestVoteResponse messages to know if it
won the election or not.  If it wins, it becomes a leader.

3. A server that becomes a "leader" resets some internal tracking
information related to the followers and then immediately sends
an AppendEntries message to all of the peers to assert its leadership.

## Testing

Testing continues to be a challenge.  However, here's an example
of the kind of thing you can do:

```
# Create the network
net = RaftNetwork(3)

# Create the servers
server0 = RaftServer(net.create_node(0), [])
server1 = RaftServer(net.create_node(1), [])
server2 = RaftServer(net.create_node(2), [])

# Have one of them become a candidate
server0.become_candidate()

# Process messages
process_messages([server0, server1, server2])

# Now verify that it became the leader and the others followers
assert server0.role == 'LEADER'
assert server1.role == server2.role == 'FOLLOWER'
```

A server may or may not be able to become a leader depending
on the state of its log.   You might try to create testing
scenarios based on figures in the paper.   For example, working
off of Figures 6 and 7.

## Edge Cases

Leader election involves a number of subtle edge cases you'll
need to be aware of.

1. Time is subdivided into "terms" which are represented by
monotonically increasing integers.  There is only one leader per term.

2. A server may only vote for a single candidate in a given term.

3. A server only grants a vote to a candidate if the candidate's log
is at least as up-to-date as itself. Read section 5.4.1 carefully.
Then read it again.

4. A newly elected leader may NEVER commit entries from a previous
term before it has committed new entries from its own term.  See
Figure 8 and section 5.4.2.

5. All messages in Raft embed the term number of the sender.  If a
message with a newer term is received, the receiver immediately
becomes a follower.  If a message with an older term is received, a
server can ignore the message (or respond with a fail/false status
response).

6. A server that is a candidate should switch to a follower
if it receives an AppendEntries message from a server with the same
term number as its own.  This can happen if two servers decided to
become a candidate at the same time, but one of the servers was
successful in getting a majority of votes.

## Commentary on Time

Notably absent from the above discussion is any mention of time, timeouts,
or heartbeats.  

Yes, time is something that needs to be handled--eventually.  For now,
consider the problem of "time" to be external to the code you're writing.
The most important method here is `become_candidate()`.  THAT is the
method that will execute when an election timeout occurs.  When it executes,
it initiates a series of messages related to voting and ultimately a
decision about leadership.   That is our primary focus in this project.



