# Project 7 - Modeling Consensus

In Project 6, you modeled log replication.  This project extends that
to determine "consensus" and to model client interaction.

## Committed Entries

A core idea in Raft is that of a "committed" log entry.  In short, log
entries are "committed" if they have been replicated across a majority
of servers in the cluster. For example, if a log entry is replicated
on 3 of 5 servers (i.e., "consensus").  

Each server maintains a "commit_index" variable that tracks the last known
log entry to be committed on that server.

```
class RaftServer:
    def __init__(self, ...):
        ...
	self.commit_index = -1
	...
```

Initially, `commit_index` is set to -1 (meaning that nothing is known).
Advancement of the index is determined solely by the leader.  This happens
in two ways.  When the leader receives an `AppendEntriesResponse` messages
from a follower, it learns how much of the log is replicated on that follower.
From that, the leader can advance the commit index as applicable (note: this
requires monitoring the state of all followers).

A follower advances its `commit_index` value when it receives a
message from the leader.  Each `AppendEntries` message encodes the
leader `commit_index` value.  If this value is greater than that on
the follower, the follower can update its `commit_index` value
accordingly.

## Applied Entries

Log entries are "committed" if they are replicated across a majority.  However,
there is a separate concept of "applied entries."   Raft, by itself, doesn't
really do anything. It's simply an algorithm that works to replicate a log.
However, in a larger application, the log represents transactions that are
actually supposed to be carried out.   For example, if implementing a
key-value store, you need to know when you can actually modify the key-value
store values.  This is the idea of an "applied entry."  Not only has the
log entry been committed, but it has been applied to the application code.

To track this, each server additionally includes an "last_applied" index.

```
class RaftServer:
    def __init__(self, ...):
        ...
	self.last_applied = -1
	...
```

The management of the `last_applied` value exists somewhat outside of
Raft itself--the Raft algorithm only provides the value.  It doesn't
do anything to update the value--that's up to the application.
Basically, the application program (i.e., the key-value store) can
watch this value and know that it's safe to process log entries anytime that
it lags behind the value of `commit_index`.  The only real
requirement is that `last_applied` should never be greater than
`commit_index`.

## Modeling Raft-Application Interaction

Eventually, we're going to use Raft to implement a key-value store.
For example, here is a basic KV-store class:

```
class KVStore:
    def __init__(self):
        self.data = { }

    def get(self, key):
        return self.data[key]

    def set(self, key, value):
        self.data[key] = value
	return 'ok'

    def delete(self, key):
        del self.data[key]
	return 'ok'
```

How would you modify this class to interact with the raft server
module that you're creating?  Specifically, how does it put
transactions on the log?   How do committed transactions later
get turned into operations on the key-value store class?

Hint: At a minimum, the class will be modified to work with
a Raft server object:

```
class KVStore:
    def __init__(self, raft):
        self.raft = raft          # Raft server component
	self.data = { }
    ...
```

However, how are the various methods modified to work with
Raft?

## Testing

Testing this part of the project is tricky and will require some thought.
Here is the basic gist of how it's supposed to work:

```
# Create a Raft network
net = RaftNetwork(3)

# Create some Raft Servers
serv0 = RaftServer(net.create_node(0), [])
serv1 = RaftServer(net.create_node(1), [])
serv2 = RaftServer(net.create_node(2), [])

# Create some KV apps on top of Raft
kv0 = KVServer(serv0)
kv1 = KVServer(serv1)
kv2 = KVServer(serv2)

# Now carry out a transaction on kv0 (the "leader")
kv0.set('foo', 'hello)

# Verify that the transaction is NOT complete initially
assert 'foo' not in kv0.data

# Have the leader append the entry on followers
serv0.send_append_entries()

# Run all of the resulting messages
process_messages([serv0, serv1, serv2])

# Assert that the transaction now took place on the leader
assert kv0.get('foo') == 'hello'
```

## Comments

The Raft-Application interface is messy and complicated.  Partly
this is an artifact of everything being delayed.  Operations
on the KV store (`get()`, `set()`, and `delete()`) don't happen
right away--they get delayed until certain things happen in the
underlying Raft module.   Coordinating the time sequencing of
this is problematic and you'll need to think about the software
architecture for it.   One possible approach is to rely upon
callback functions.  For example, the KV-store could register a
callback that gets triggered when transactions are ready to
execute.  
  

 

