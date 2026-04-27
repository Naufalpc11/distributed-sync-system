import argparse
from src.nodes.base_node import BaseNode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peers", nargs="*", default=[])

    args = parser.parse_args()

    node = BaseNode(
        node_id=args.id,
        host="localhost",
        port=args.port,   # 🔥 INI YANG PENTING
        peers=args.peers
    )

    node.run()

if __name__ == "__main__":
    main()