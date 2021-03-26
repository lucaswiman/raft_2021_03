#!/usr/bin/env python
from __future__ import annotations

import argparse, functools, logging, sched, socket, sys, time
from queue import Queue
from threading import Thread
from typing import NamedTuple, Optional
from urllib.parse import urlparse

from raft_core import ClockTick, Event, Message, RaftConfig, RaftNode


logger = logging.getLogger("server")
errors: Queue[Exception] = Queue()


class UDPAddress(NamedTuple):
    host: str
    port: int

    @classmethod
    def parse_uri(cls, addr: str) -> UDPAddress:
        """
        Parse a url like udp://127.0.0.1:5000 into ("127.0.0.1", 5000)
        """
        parsed = urlparse(addr)
        if not parsed.hostname or not parsed.port:
            raise ValueError(addr)
        return UDPAddress(parsed.hostname, parsed.port)

    def receive(self):
        """
        Serve on this port.

        Assumes that self.host refers to this host, but host is not otherwise
        used.

        Returns a generator that accepts bytestrings and encodes them for
        transport over the wire.
        """

        def get_client_socket():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            sock.bind(("", self.port))
            sock.listen()
            client, addr = sock.accept()
            return client, sock

        client, sock = get_client_socket()
        try:
            while True:
                size_chars = ""
                size: Optional[int] = None
                while True:
                    char = client.recv(1)
                    if char == b"":
                        # Disconnection
                        break
                    if char.isdigit():
                        size_chars += char.decode("ascii")
                    elif char == b":":
                        size = int(size_chars)
                        break
                    else:
                        raise ValueError(f"Invalid character for size prefix: {char=}")
                if size is not None:
                    yield client.recv(size)
                sock.close()
                client, sock = get_client_socket()
        finally:
            try:
                sock.close()
            except Exception as e:
                logger.exception(e)

    def send(self):
        """
        Sends to this address.

        Returns a generator that accepts bytestrings from the wire and decodes
        them as messages.
        """
        import select

        # https://stackoverflow.com/questions/17386487/python-detect-when-a-socket-disconnects-for-any-reason

        def get_socket():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            return sock

        sock = None
        message: bytes
        while True:
            message = yield
            if sock is not None:
                try:
                    ready_to_read, ready_to_write, in_error = select.select([sock], [sock], [], 5)
                except select.error:
                    sock.shutdown(1)  # 0 = done receiving, 1 = done sending, 2 = both
                    sock.close()
                    sock = None
                else:
                    if len(ready_to_write) == 0:
                        sock.shutdown(1)  # 0 = done receiving, 1 = done sending, 2 = both
                        sock.close()
                        sock = None
            if sock is None:
                logger.debug("Connecting send socket: %s", self)
                try:
                    sock = get_socket()
                except ConnectionRefusedError:
                    logger.warning("Unable to connect to %s", self)
                    continue
            encoded: bytes = b"%s:%s" % (str(len(message)).encode(), message)
            logger.info("Sending: %r", encoded)
            try:
                sock.send(encoded)
            except BrokenPipeError:
                sock.close()
                sock = None


def exc_logged(func):
    @functools.wraps(func)
    def logged_func(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            errors.put(e)
            logger.exception(e)
            raise
        return func(*args, **kwargs)

    return logged_func


@exc_logged
def process_events(config: RaftConfig, node: RaftNode):
    """
    Handle events (incoming messages and clockticks).
    """
    while True:
        event = node.events.get()
        node.process_event(event)


@exc_logged
def clock(event_queue: Queue[Event], clocktick_ms=10):
    """
    Enqueues clockticks at regular clocktick_ms intervals.
    """

    def enqueue_clocktick():
        event_queue.put(ClockTick())

    start_time = time.monotonic()
    ms = 1 / 1000
    s = sched.scheduler(time.monotonic, time.sleep)
    next_time = start_time
    while True:
        next_time = next_time + clocktick_ms * ms
        s.enterabs(next_time, priority=1, action=enqueue_clocktick)
        s.run()


@exc_logged
def receive(uri: str, event_queue: Queue[Event]):
    addr: UDPAddress = UDPAddress.parse_uri(uri)
    for message in addr.receive():
        event_queue.put(Message.from_bytes(message))


@exc_logged
def send_messages(config: RaftConfig, messages: Queue[Message]):
    id_to_receiver = {}
    while True:
        message = messages.get()
        recipient_id = message.recipient_id
        if recipient_id not in id_to_receiver:
            address = UDPAddress.parse_uri(config.addresses[recipient_id])
            id_to_receiver[recipient_id] = address.send()

            # Generators need to be sent an empty value first.
            # Sort of annoying.
            id_to_receiver[recipient_id].send(None)
        id_to_receiver[recipient_id].send(bytes(message))


def serve(config: RaftConfig, node: RaftNode, clocktick_ms):
    threads = [
        Thread(target=send_messages, args=(config, node.outgoing_messages), daemon=True),
        Thread(target=process_events, args=(config, node), daemon=True),
        Thread(target=clock, args=(node.events, clocktick_ms), daemon=True),
        Thread(target=receive, args=(config.addresses[node.id], node.events), daemon=True),
        Thread(target=send_messages, args=(config, node.outgoing_messages), daemon=True),
    ]

    for thread in threads:
        thread.start()
    error = errors.get()
    if error:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serves a single raft server instance.")
    parser.add_argument("server_id", type=int, help="Which server_to_start [0-num_servers].")
    parser.add_argument("--config-file", type=str, default="./config.json")
    parser.add_argument("--verbosity", type=int, default=0, help="0=warning, 1=info, 2=debug")
    parser.add_argument(
        "--clocktick-ms", type=int, default=10, help="Length of a clocktick, default (10ms)"
    )
    args = parser.parse_args()
    log_format_string = "%(asctime)s:%(name)s:%(levelname)s:%(threadName)s: %(message)s"
    level = [logging.WARNING, logging.INFO, logging.DEBUG][args.verbosity]
    logging.basicConfig(level=level, format=log_format_string)

    config = RaftConfig.from_config(args.config_file)
    node = config.build_node(args.server_id)
    serve(config, node, clocktick_ms=args.clocktick_ms)
