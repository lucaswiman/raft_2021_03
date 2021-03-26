#!/usr/bin/env python
from __future__ import annotations

import argparse, functools, logging, sys
from queue import Queue
from threading import Thread

from raft_core import Message, RaftConfig, RaftNode


logger = logging.getLogger("server")
errors = Queue()

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
        raise NotImplementedError()


def serve(config: RaftConfig, node: RaftNode):
    threads = [
        Thread(target=send_messages, args=(config, node.outgoing_messages), daemon=True),
    ]
    for thread in threads:
        thread.start()
    error = errors.get()
    if error:
        sys.exit(1)


if __name__ == "__main__":
    log_format_string = "%(asctime)s:%(name)s:%(levelname)s:%(threadName)s: %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format_string)
    parser = argparse.ArgumentParser(description="Serves a single raft server instance.")
    parser.add_argument("server_id", type=int, help="Which server_to_start [0-num_servers].")
    parser.add_argument("--config-file", type=str, default="./config.json")
    args = parser.parse_args()
    config = RaftConfig.from_config(args.config_file)
    node = config.build_node(args.server_id)
    serve(config, node)