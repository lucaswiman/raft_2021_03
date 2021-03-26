#!/usr/bin/env python
from __future__ import annotations

import argparse, functools, logging, sched, socket, sys, time
from queue import Queue
from threading import Thread
from typing import NamedTuple, Optional
from urllib.parse import urlparse

from raft_core import ClockTick, Event, Message, RaftConfig, RaftNode


logger = logging.getLogger("client")


def raft_get(key):
    print(f"got {key}")


def raft_set(key, val):
    print(f"set {key}={val}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serves a single raft server instance.")
    parser.add_argument("command", type=str, help="get|set")
    parser.add_argument("key", type=str)
    parser.add_argument("val", type=str, nargs="?")
    parser.add_argument("--config-file", type=str, default="./config.json")
    parser.add_argument("--verbosity", type=int, default=0, help="0=warning, 1=info, 2=debug")
    args = parser.parse_args()
    log_format_string = "%(asctime)s:%(name)s:%(levelname)s:%(threadName)s: %(message)s"
    level = [logging.WARNING, logging.INFO, logging.DEBUG][args.verbosity]
    logging.basicConfig(level=level, format=log_format_string)
    
    config = RaftConfig.from_config(args.config_file)
    if args.command == "get":
        success = raft_get(args.key)
    elif args.command == "set":
        success = raft_set(args.key, args.val)
    else:
        print(f"invalid command {args.command}")
        success = False
    sys.exit(0 if success else 1)
