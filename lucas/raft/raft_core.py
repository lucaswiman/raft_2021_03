from __future__ import annotations
import json, queue
from dataclasses import asdict, dataclass, field
from typing import cast, Dict, List, Literal, Optional, Tuple, Union

from log import LogEntry, ItemType, append_entries


@dataclass
class RaftConfig:
    # Nodes are labeled 0, 1, ..., with the id corresponding to the position in addresses.
    addresses: List[str]
    initial_leader: int = 0

    def build_servers(self) -> List[RaftServer]:
        servers = [
            RaftServer(id=id, log=[], num_servers=len(self.addresses))
            for id, address in enumerate(self.addresses)
        ]
        servers[self.initial_leader].become_leader()
        return servers


RPCMethod = Literal[
    "follower_append_entries",
    "leader_append_entries_response",
    "leader_append_entries",
    "client_add_entry",
    "request_vote",
    "request_vote_response",
]
RPC_METHODS = frozenset(RPCMethod.__args__)  # type: ignore


@dataclass
class Message:
    sender_id: int
    recipient_id: int
    method_name: RPCMethod
    args: dict  # should be json-serializable
    current_term: int

    @classmethod
    def from_bytes(cls, b: bytes):
        return cls(**json.loads(b.decode("utf-8")))

    def __bytes__(self):
        return json.dumps(asdict(self)).encode("utf-8")


@dataclass
class ClockTick:
    pass


Event = Union[Message, ClockTick]


def compute_commit_index(match_index: List[int]):
    """
    Compute the commit index as the largest MatchIndex present on a majority of servers.

    This is _almost_ the median, unless the list has an even length.
    """
    sorted_indexes = sorted(match_index, reverse=True)
    # There would be a +1 here to get the index representing the majority,
    # but since python is 0-indexed, it gets subtracted away.
    # e.g. for n=2, we want the 2nd index, which is 1.
    return sorted_indexes[len(sorted_indexes) // 2]


RoleName = Literal["LEADER", "FOLLOWER", "CANDIDATE"]


@dataclass
class RaftServer:
    id: int

    num_servers: int
    log: List[LogEntry]

    role: RoleName = "FOLLOWER"

    ####################### VOLATILE FIELDS ON LEADERS #######################
    # From the spec:
    # > for each server, index of the next log entry to send to that server
    # > (initialized to leader last log index + 1)
    next_index: Optional[List[int]] = None

    # From the spec:
    # > for each server, index of highest log entry known to be replicated on
    # > server (initialized to 0, increases monotonically)
    match_index: Optional[List[int]] = None
    ####################### END OF LEADER FIELDS #############################

    voted_for: Optional[int] = None

    # For candidates to receive vote tallies. Not mentioned in figure 2, but implied by
    # needing to count votes.
    votes: Optional[Dict[int, bool]] = None

    _current_term: int = 1
    _commit_index: int = 0
    outgoing_messages: queue.Queue[Message] = field(default_factory=queue.Queue)
    events: queue.Queue[Event] = field(default_factory=queue.Queue)

    application_index: int = 0
    applications: queue.Queue[List[ItemType]] = field(default_factory=queue.Queue)

    @property
    def is_leader(self) -> bool:
        return self.role == "LEADER"

    def become_leader(self):
        self.role = "LEADER"
        self.next_index = [len(self.log) + 1] * self.num_servers
        self.match_index = [0] * self.num_servers
        self.votes = None

    def become_follower(self):
        self.role = "FOLLOWER"
        self.next_index = None
        self.match_index = None
        self.votes = None

    def become_candidate(self):
        self.role = "CANDIDATE"
        self.next_index = None
        self.match_index = None
        self.votes = {}
        self.votes[self.id] = True
        self.current_term += 1
        self.candidate_request_votes()

    @property
    def current_term(self):
        return self._current_term

    @current_term.setter
    def current_term(self, new_term):
        if new_term == self.current_term:
            return
        if self.role == "CANDIDATE":
            self.voted_for = self.id
        else:
            self.voted_for = None
        self._current_term = new_term

    @property
    def peers(self):
        return [i for i in range(self.num_servers) if i != self.id]

    def process_event(self, event: Event):
        if isinstance(event, ClockTick):
            raise NotImplementedError()
        elif isinstance(event, Message):
            message = cast(Message, event)
            if message.method_name not in RPC_METHODS:
                raise ValueError(f"Unhandled method {message.method_name=}")

            if message.current_term < self.current_term:
                # Figure 2: all RPCs should be rejected if the message term is lower than
                # the current term. #OldNews
                # TODO: spec says "Reply false" if this case happens. Should this be a message?
                return
            elif message.current_term > self.current_term:
                # Figure 4: The role state machine should transition to follower whenever it
                # sees a higher term.
                self.current_term = message.current_term
                self.become_follower()

            getattr(self, message.method_name)(sender_id=message.sender_id, **message.args)

        else:
            raise TypeError(type(event))

    def client_add_entry(self, item: ItemType):
        if not self.is_leader:
            return False
        if self.next_index is None:
            raise AssertionError("Bug!")
        next_index = self.next_index[self.id]
        prev_index = next_index - 1
        prev_term = self.log[-1].term if self.log else 0
        return self.leader_append_entries(
            prev_index, prev_term, [LogEntry(term=self.current_term, item=item)]
        )

    @property
    def commit_index(self):
        return self._commit_index

    @commit_index.setter
    def commit_index(self, new_commit_index):
        prev = self._commit_index
        self._commit_index = new_commit_index
        if prev != new_commit_index:
            self.applications.put([entry.item for entry in self.log[prev:new_commit_index]])
            self.application_index = new_commit_index

    def leader_set_commit_index(self):
        self.commit_index = compute_commit_index(self.match_index)

    def leader_append_entries(self, prev_index: int, prev_term: int, entries: List[LogEntry]):
        if not self.is_leader:
            # In the paper, a follower should direct this to the leader
            raise ValueError("Must be leader to call this method.")
        if self.next_index is None:
            raise AssertionError("Bug!")
        success = append_entries(self.log, prev_index, prev_term, entries)
        self.next_index[self.id] = len(self.log) + 1
        return success

    def send_append_entries_to_peer(self, peer):
        next_index = self.next_index[peer]
        prev_index = next_index - 1
        assert prev_index >= 0
        if prev_index == 0:
            prev_term = 0
        else:
            prev_term = self.log[prev_index - 1].term
        new_entries = self.log[next_index - 1 :]
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=peer,
                method_name="follower_append_entries",
                current_term=self.current_term,
                args={
                    "prev_index": prev_index,
                    "prev_term": prev_term,
                    "entries": [entry._asdict() for entry in new_entries],
                    "commit_index": self.commit_index,
                },
            )
        )

    def send_append_entries(self):
        # Send an AppendEntries message to all peers to update their logs
        for peer in self.peers:
            self.send_append_entries_to_peer(peer)

    def follower_append_entries(
        self,
        sender_id: int,
        prev_index: int,
        prev_term: int,
        entries: List[dict],
        commit_index: int,
    ):
        # Process an AppendEntries messages sent by the leader
        success = append_entries(
            self.log, prev_index, prev_term, [LogEntry(**entry) for entry in entries]
        )
        match_index: Optional[int] = None
        if success:
            # https://github.com/ongardie/raft.tla/blob/974fff7236545912c035ff8041582864449d0ffe/raft.tla#L368-L369
            match_index = prev_index + len(entries)
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=sender_id,
                method_name="leader_append_entries_response",
                args={"match_index": match_index},
                current_term=self.current_term,
            )
        )
        self.commit_index = commit_index

    def leader_append_entries_response(self, sender_id: int, match_index: Optional[int]):
        # Process an AppendEntriesResponse message sent by a follower
        if not self.is_leader:
            # Probably an old message and I've been voted off the island.
            return
        if self.next_index is None or self.match_index is None:
            raise AssertionError("Bug!")
        if match_index is not None:
            # AppendEntries on msg.source worked!
            self.next_index[sender_id] = match_index + 1
            self.match_index[sender_id] = match_index
            self.leader_set_commit_index()
        else:
            self.next_index[sender_id] -= 1
            self.send_append_entries_to_peer(sender_id)

    def get_last_term_and_index(self) -> Tuple[int, int]:
        last_log_index = len(self.log)
        if last_log_index == 0:
            last_log_term = 0
        else:
            last_log_term = self.log[last_log_index - 1].term
        return last_log_term, last_log_index

    def request_vote_from_peer(self, peer: int):
        last_log_term, last_log_index = self.get_last_term_and_index()
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=peer,
                method_name="request_vote",
                args={
                    "last_log_index": last_log_index,
                    "last_log_term": last_log_term,
                },
                current_term=self.current_term,
            )
        )

    def candidate_request_votes(self):
        for peer in self.peers:
            self.request_vote_from_peer(peer)

    def request_vote(self, sender_id, last_log_index: int, last_log_term: int):
        """
        > If votedFor is null or candidateId, and candidate’s log is at least as
        > up-to-date as receiver’s log, grant vote (§5.2, §5.4)
        """
        if self.voted_for is not None:
            vote = self.voted_for == sender_id
        else:
            vote = (last_log_term, last_log_index) >= self.get_last_term_and_index()
            if vote:
                self.voted_for = sender_id
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=sender_id,
                method_name="request_vote_response",
                current_term=self.current_term,
                args={
                    "vote": vote,
                },
            )
        )

    def request_vote_response(self, sender_id, vote: bool):
        if self.role != "CANDIDATE":
            # A delayed vote after winning the election.
            return
        votes = cast(Dict, self.votes)
        votes[sender_id] = vote
        if sum(votes.values()) > self.num_servers // 2:
            self.become_leader()
            self.send_append_entries()
