#!/usr/bin/env python
from __future__ import annotations

import argparse, functools, json, logging, sched, socket, sys, time
from queue import Queue
from threading import Thread
from typing import NamedTuple, Optional
from urllib.parse import urlparse

import requests

from raft_core import ClockTick, Event, Message, RaftConfig, RaftNode
from server import UDPAddress


logger = logging.getLogger("client")


def raft_get(key: str, config: RaftConfig):
    for address in config.client_addresses:
        try:
            response = requests.get(f"{address}/get/{key}")
        except Exception as e:
            logger.debug(f"Failed to contact {address}")
        else:
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 412:
                logger.debug("%s is not the leader.", address)
            else:
                # TODO
                logger.error("Unhandled status code %s", response.status_code)
                return False, None
    logger.error("Failed to find leader.")
    return False, None


def raft_set(key: str, val: str, config: RaftConfig):
    for address in config.client_addresses:
        try:
            response = requests.post(f"{address}/set/{key}", json=val)
        except Exception as e:
            logger.debug(f"Failed to contact {address}")
        else:
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 412:
                logger.debug("%s is not the leader.", address)
            else:
                # TODO
                logger.error("Unhandled status code %s", response.status_code)
                return False, None
    logger.error("Failed to find leader.")
    return False, None


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
        success, value = raft_get(args.key, config)
        print(value)
    elif args.command == "set":
        success = raft_set(args.key, args.val, config)
    else:
        print(f"invalid command {args.command}")
        success = False
    sys.exit(0 if success else 1)
