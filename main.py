import argparse

from src.nodes.base_node import BaseNode
from src.utils.config import Config, load_env_file


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--id", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--advertise-host", default=None)
    parser.add_argument("--peers", nargs="*", default=None)
    return parser


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env-file", default=".env")
    pre_args, _ = pre_parser.parse_known_args()

    load_env_file(pre_args.env_file)

    parser = build_parser()
    args = parser.parse_args()
    env_config = Config.from_env()

    node = BaseNode(
        node_id=args.id or env_config["node_id"],
        bind_host=args.host or env_config["bind_host"],
        port=args.port or env_config["port"],
        peers=args.peers if args.peers is not None else env_config["peers"],
        advertise_host=args.advertise_host or env_config["advertise_host"],
    )

    node.run()


if __name__ == "__main__":
    main()
