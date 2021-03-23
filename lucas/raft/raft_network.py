from __future__ import annotations

from typing import Dict, Protocol, Optional, List
import random
from dataclasses import dataclass


class Network(Protocol):
    num_nodes: int
    nodes: Dict[int, RaftNode]

    def create_node(self, node_id) -> RaftNode:
        ...

    def send(self, node_id: int, message: bytes) -> None:
        ...

    def _receive(self, node_id) -> Optional[bytes]:
        """
        Receives exactly one message for the given node_id.

        This should raise an error if node_id is not controlled by this
        Network object (e.g. is running on a different server).
        """
        ...


class RaftNode(Protocol):
    node_id: int
    network: Network

    def send(self, node_id: int, message: bytes):
        ...

    def receive(self) -> Optional[bytes]:
        ...


@dataclass(repr=True)
class Node(RaftNode):
    node_id: int
    network: Network

    def send(self, node_id: int, message: bytes):
        self.network.send(node_id, message)

    def receive(self) -> Optional[bytes]:
        return self.network._receive(self.node_id)


class MockNetwork(Network):
    num_nodes: int
    nodes: Dict[int, RaftNode]

    def __init__(self, num_servers, random=random):
        self.num_nodes: int = num_servers
        self.nodes: Dict[int, RaftNode] = {}
        self.server_to_messages: Dict[int, List[bytes]] = {}
        self.shuffle_messages = False
        self.disabled_nodes = set()
        # Can be swapped with hypothesis random or whatever.
        self.random = random
        self.message_failure_rate = 0.0

    def __repr__(self):
        return f"MockNetwork({self.num_servers})"

    def disable(self, node_id: int):
        self.disabled_nodes.add(node_id)

    def enable(self, node_id: int):
        try:
            self.disabled_nodes.remove(node_id)
        except KeyError:
            pass

    def create_node(self, node_id) -> RaftNode:
        if node_id not in range(self.num_nodes):
            raise ValueError(node_id)
        self.server_to_messages[node_id] = []
        return Node(node_id=node_id, network=self)

    def send(self, node_id: int, message: bytes):
        if node_id in self.server_to_messages:
            if self.random.random() >= self.message_failure_rate / 2:
                self.server_to_messages[node_id].append(message)
        # Otherwise, yolo, the network sucks.

    def _receive(self, node_id) -> Optional[bytes]:
        if node_id in self.disabled_nodes:
            return None
        messages = self.server_to_messages[node_id]
        if self.random.random() < self.message_failure_rate / 2:
            return None
        if self.shuffle_messages:
            self.random.shuffle(messages)
            return messages.pop()
        else:
            return messages.pop(0)  # O(n)
