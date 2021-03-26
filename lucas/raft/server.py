#!/usr/bin/env python
from __future__ import annotations

import argparse, functools, logging, sched, sys, time
from queue import Queue
from threading import Thread

from raft_core import ClockTick, Event, Message, RaftConfig, RaftNode


logger = logging.getLogger("server")
errors: Queue[Exception] = Queue()


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
def send_messages(config: RaftConfig, queue: Queue[Message]):
    """
    Handle the outgoing messages queue.
    """
    while True:
        message = queue.get()
        print(message)


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


def serve(config: RaftConfig, node: RaftNode):
    threads = [
        Thread(target=send_messages, args=(config, node.outgoing_messages), daemon=True),
        Thread(target=process_events, args=(config, node), daemon=True),
        Thread(target=clock, args=(node.events,), daemon=True),
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
    args = parser.parse_args()
    log_format_string = "%(asctime)s:%(name)s:%(levelname)s:%(threadName)s: %(message)s"
    level = [logging.WARNING, logging.INFO, logging.DEBUG][args.verbosity]
    logging.basicConfig(level=level, format=log_format_string)

    config = RaftConfig.from_config(args.config_file)
    node = config.build_node(args.server_id)
    serve(config, node)
