import asyncio
from src.nodes.base_node import BaseNode

async def main():
    node = BaseNode(port=8000)
    await node.start()

if __name__ == "__main__":
    asyncio.run(main())