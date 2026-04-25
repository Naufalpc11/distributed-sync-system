import asyncio
import uuid

class BaseNode:
    def __init__(self, node_id=None, host="localhost", port=8000):
        self.node_id = node_id or str(uuid.uuid4())
        self.host = host
        self.port = port
        self.peers = []

    async def start(self):
        print(f"Node {self.node_id} running at {self.host}:{self.port}")

    async def send_message(self, peer, message):
        print(f"[{self.node_id}] Sending message to {peer}: {message}")