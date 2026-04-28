import argparse
from src.nodes.base_node import BaseNode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--advertise-host", default=None)
    parser.add_argument("--peers", nargs="*", default=[])

    args = parser.parse_args()

    node = BaseNode(
        node_id=args.id,
        bind_host=args.host,
        port=args.port,
        peers=args.peers,
        advertise_host=args.advertise_host or args.host,
    )

    node.run()

if __name__ == "__main__":
    main()