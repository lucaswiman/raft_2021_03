#!/usr/bin/env python
import argparse, logging

from raft_core import RaftConfig, RaftNode


def serve(config: RaftConfig, node: RaftNode):
    pass

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