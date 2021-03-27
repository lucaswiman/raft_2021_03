from __future__ import annotations
import json, logging, queue, pathlib, random, time
from dataclasses import asdict, dataclass, field
from typing import cast, Dict, List, Literal, Optional, Tuple, Union

from log import LogEntry, ItemType, append_entries


logger = logging.getLogger("raft")


@dataclass
class RaftConfig:
    # Nodes are labeled 0, 1, ..., with the id corresponding to the position in addresses.
    addresses: List[str]
    initial_leader: int = 0
    client_addresses: Optional[List[str]] = None

    @classmethod
    def from_config(cls, file: str) -> RaftConfig:
        return RaftConfig(**json.loads(pathlib.Path(file).read_text()))

    def build_node(self, id):
        return RaftNode(id=id, log=[], num_nodes=len(self.addresses))

    def build_nodes(self) -> List[RaftNode]:
        # Used for debugging / testing.
        nodes = [self.build_node(id) for id, address in enumerate(self.addresses)]
        nodes[self.initial_leader].become_leader()
        return nodes


RPCMethod = Literal[
    "follower_append_entries",
    "leader_append_entries_response",
    "leader_append_entries",
    "client_add_entry",
    "request_vote",
    "request_vote_response",
    "reject_message",
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


def current_time_ms():
    return time.time_ns() // 1_000_000


PROCESS_START_TIME_MS = current_time_ms()


@dataclass
class ClockTick:
    ms: int = field(default_factory=lambda: current_time_ms() - PROCESS_START_TIME_MS)


Event = Union[Message, ClockTick]


def compute_majority_match_index(match_index: List[int]):
    """
    Compute the commit index as the largest MatchIndex present on a majority of node.

    This is _almost_ the median, unless the list has an even length.
    """
    sorted_indexes = sorted(match_index, reverse=True)
    # There would be a +1 here to get the index representing the majority,
    # but since python is 0-indexed, it gets subtracted away.
    # e.g. for n=2, we want the 2nd index, which is 1.
    return sorted_indexes[len(sorted_indexes) // 2]


def random_election_clockticks(lower=100, upper=200):
    """
    Generate a new random election timeout.

    One clocktick = 10ms.
    """
    return random.randint(lower, upper)


RoleName = Literal["LEADER", "FOLLOWER", "CANDIDATE"]


@dataclass
class RaftNode:
    id: int

    num_nodes: int
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

    # Number of clockticks needed to create an election.
    # Should be re-randomized every time an election timeout occurs.
    election_timeout_clockticks: int = field(default_factory=random_election_clockticks)
    # Timer is reset on every election and every heartbeat.
    clockticks_since_last_reset: int = 0
    # Per the paper, this should be an order of magnitude less than
    # election_timeout_clockticks.
    clockticks_between_heartbeats: int = 5  # 50ms

    @property
    def is_leader(self) -> bool:
        return self.role == "LEADER"

    def become_leader(self):
        logger.warning("Node %s became LEADER, term %s.", self.id, self.current_term)
        self.role = "LEADER"
        self.next_index = [len(self.log) + 1] * self.num_nodes
        self.match_index = [0] * self.num_nodes
        self.match_index[self.id] = len(self.log)
        self.votes = None

    def become_follower(self):
        logger.warning("Node %s became FOLLOWER, term %s.", self.id, self.current_term)
        self.role = "FOLLOWER"
        self.next_index = None
        self.match_index = None
        self.votes = None

    def become_candidate(self):
        logger.warning("Node %s became CANDIDATE, term %s.", self.id, self.current_term)
        # This also doubles as the "election timeout" handler.
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
        self.election_timeout_clockticks = random_election_clockticks()
        if self.role == "CANDIDATE":
            self.voted_for = self.id
        else:
            self.voted_for = None
        self._current_term = new_term

    @property
    def peers(self):
        return [i for i in range(self.num_nodes) if i != self.id]

    def process_event(self, event: Event):
        if isinstance(event, ClockTick):
            logger.debug("Processing clocktick: %r", event)
            self.clockticks_since_last_reset += 1
            if self.is_leader:
                if self.clockticks_since_last_reset >= self.clockticks_between_heartbeats:
                    # append_entries is what raft uses as a heartbeat.
                    self.send_append_entries()
            elif self.clockticks_since_last_reset >= self.election_timeout_clockticks:
                self.become_candidate()
        elif isinstance(event, Message):
            logger.debug("Processing message: %r", event)
            message = cast(Message, event)
            if message.method_name not in RPC_METHODS:
                raise ValueError(f"Unhandled method {message.method_name=}")

            if message.current_term < self.current_term:
                # Figure 2: all RPCs should be rejected if the message term is lower than
                # the current term. #OldNews
                # TODO: spec says "Reply false" if this case happens. Should this be a message?
                logger.warning(f"Rejected message: {message}, current_term={self.current_term}")
                self.outgoing_messages.put(Message(
                    sender_id=self.id,
                    recipient_id=message.sender_id,
                    method_name="reject_message",
                    current_term=self.current_term,
                    args={},
                ))
                return
            elif message.current_term > self.current_term:
                # Figure 4: The role state machine should transition to follower whenever it
                # sees a higher term.
                logger.warning(
                    f"Newer message: updating {self.current_term} to {message.current_term}."
                )

                # Ordering is very important in the next two lines, since a candidate is demoted
                # to a follower on a newer term, but candidates always vote for themselves in
                # every term. If the ordering is reversed, the candidate will vote for itself
                # despite there being a newer term, which can lead to infinite loops.
                self.become_follower()
                self.current_term = message.current_term

            getattr(self, message.method_name)(sender_id=message.sender_id, **message.args)

        else:
            raise TypeError(type(event))

    def client_add_entry(self, item: ItemType):
        if not self.is_leader:
            return False
        if self.next_index is None or self.match_index is None:
            raise AssertionError("Bug!")
        next_index = self.next_index[self.id]
        prev_index = next_index - 1
        prev_term = self.log[-1].term if self.log else 0
        self.match_index[self.id] = len(self.log)
        success = self.leader_append_entries(
            prev_index, prev_term, [LogEntry(term=self.current_term, item=item)]
        )
        if success:
            return {
                "current_term": self.current_term,
                "index": len(self.log),
            }
        else:
            return None

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
        majority_match_index = compute_majority_match_index(self.match_index)
        if majority_match_index > self.commit_index:
            # This log entry has been replicated on a majority of nodes.
            # However, we cannot update the commit_index to a previous term's
            # record. See "Figure 8" tests for reasoning why not.
            if self.log[majority_match_index - 1].term < self.current_term:
                return
            self.commit_index = majority_match_index

    def leader_append_entries(self, prev_index: int, prev_term: int, entries: List[LogEntry]):
        if not self.is_leader:
            # In the paper, a follower should direct this to the leader
            raise ValueError("Must be leader to call this method.")
        if self.next_index is None or self.match_index is None:
            raise AssertionError("Bug!")
        success = append_entries(self.log, prev_index, prev_term, entries)
        self.next_index[self.id] = len(self.log) + 1
        self.match_index[self.id] = len(self.log)
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
        assert self.is_leader, "bug"
        self.clockticks_since_last_reset = 0
        for peer in self.peers:
            self.send_append_entries_to_peer(peer)

    def reject_message(self, sender_id):
        # only exists to update terms.
        pass

    def follower_append_entries(
        self,
        sender_id: int,
        prev_index: int,
        prev_term: int,
        entries: List[dict],
        commit_index: int,
    ):
        self.clockticks_since_last_reset = 0
        # Process an AppendEntries messages sent by the leader
        success = append_entries(
            self.log, prev_index, prev_term, [LogEntry(**entry) for entry in entries]
        )
        match_index: Optional[int] = None
        if success:
            # https://github.com/ongardie/raft.tla/blob/974fff7236545912c035ff8041582864449d0ffe/raft.tla#L368-L369
            match_index = prev_index + len(entries)
            self.commit_index = commit_index
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=sender_id,
                method_name="leader_append_entries_response",
                args={"match_index": match_index},
                current_term=self.current_term,
            )
        )

    def leader_append_entries_response(self, sender_id: int, match_index: Optional[int]):
        # Process an AppendEntriesResponse message sent by a follower
        if not self.is_leader:
            # Probably an old message and I've been voted off the island.
            return
        if self.next_index is None or self.match_index is None:
            raise AssertionError("Bug!")
        if match_index is not None:
            # AppendEntries worked!
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
        self.clockticks_since_last_reset = 0
        for peer in self.peers:
            self.request_vote_from_peer(peer)

    def request_vote(self, sender_id, last_log_index: int, last_log_term: int):
        """
        > If votedFor is null or candidateId, and candidate’s log is at least as
        > up-to-date as receiver’s log, grant vote (§5.2, §5.4)
        """
        if self.voted_for is not None:
            logger.debug(f"Voting for {self.voted_for} for {sender_id}; {self.id}")
            vote = (self.voted_for == sender_id)
        else:
            logger.debug(f"Vote considerations:\n\t Message:{last_log_term=}, {last_log_index=}\n\tSelf: {self.get_last_term_and_index()=}")
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
        if sum(votes.values()) > self.num_nodes // 2:
            self.become_leader()
            self.send_append_entries()
