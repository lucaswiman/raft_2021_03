from __future__ import annotations
import json, queue
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Union

from log import LogEntry, ItemType, append_entries


@dataclass
class RaftConfig:
    # Nodes are labeled 0, 1, ..., with the id corresponding to the position in addresses.
    addresses: List[str]
    initial_leader: int = 0

    def build_servers(self) -> List[RaftServer]:
        return [
            RaftServer(
                id=id,
                next_index=[1] * len(self.addresses),  # 1-indexed
                is_leader=(id == self.initial_leader),
                log=[],
            )
            for id, address in enumerate(self.addresses)
        ]


RPCMethod = Literal[
    "follower_append_entries",
    "leader_append_entries_response",
    "leader_append_entries",
    "client_add_entry",
]
RPC_METHODS = frozenset(RPCMethod.__args__)  # type: ignore


@dataclass
class Message:
    sender_id: int
    recipient_id: int
    method_name: RPCMethod
    args: dict  # should be json-serializable

    @classmethod
    def from_bytes(cls, b: bytes):
        return json.loads(b.decode("utf-8"))

    def __bytes__(self):
        return json.dumps(self.asdict()).encode("utf-8")


@dataclass
class ClockTick:
    pass


Event = Union[Message, ClockTick]


@dataclass
class RaftServer:
    id: int
    next_index: List[int]
    is_leader: bool
    log: List[LogEntry]
    current_term: int = 1
    outgoing_messages: queue.Queue[Message] = field(default_factory=queue.Queue)
    events: queue.Queue[Event] = field(default_factory=queue.Queue)

    @property
    def peers(self):
        return [i for i, _ in enumerate(self.next_index) if i != self.id]

    def process_event(self, event: Event):
        if isinstance(event, ClockTick):
            raise NotImplementedError()
        elif isinstance(event, Message):
            raise NotImplementedError()
        else:
            raise TypeError(type(event))

    def client_add_entry(self, item: ItemType):
        next_index = self.next_index[self.id]
        prev_index = next_index - 1
        prev_term = self.log[-1].term if self.log else 0
        return self.leader_append_entries(
            prev_index, prev_term, [LogEntry(term=self.current_term, item=item)]
        )

    def leader_append_entries(self, prev_index: int, prev_term: int, entries: List[LogEntry]):
        if not self.is_leader:
            # In the paper, a follower should direct this to the leader
            raise ValueError("Must be leader to call this method.")
        success = append_entries(self.log, prev_index, prev_term, entries)
        self.next_index[self.id] = len(self.log) + 1
        return success

    def send_append_entries_to_peer(self, peer):
        next_index = self.next_index[peer]
        prev_index = next_index - 1
        prev_entry = self.log[prev_index - 1]
        new_entries = self.log[next_index - 1 :]
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=peer,
                method_name="follower_append_entries",
                args={
                    "prev_index": prev_index,
                    "prev_term": prev_entry.term,
                    "entries": [entry.asdict() for entry in new_entries],
                },
            )
        )

    def send_append_entries(self):
        # Send an AppendEntries message to all peers to update their logs
        for peer in self.peers:
            self.send_append_entries_to_peer(peer)

    def follower_append_entries(
        self, sender_id: int, prev_index: int, prev_term: int, entries: List[dict]
    ):
        # Process an AppendEntries messages sent by the leader
        success = append_entries(
            self.log, prev_index, prev_term, [LogEntry(**entry) for entry in entries]
        )
        next_index: Optional[int] = None
        if success:
            next_index = prev_index + len(entries) + 1
        self.outgoing_messages.put(
            Message(
                sender_id=self.id,
                recipient_id=sender_id,
                method_name="leader_append_entries_response",
                args={"next_index": next_index},
            )
        )

    def leader_append_entries_response(self, sender_id: int, next_index: Optional[int]):
        # Process an AppendEntriesResponse message sent by a follower
        if next_index is not None:
            # AppendEntries on msg.source worked!
            self.next_index[sender_id] = next_index
        else:
            self.next_index[sender_id] -= 1
            self.send_append_entries_to_peer(sender_id)
