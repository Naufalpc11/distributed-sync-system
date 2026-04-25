import random
import asyncio

class RaftNode:
    def __init__(self, node_id):
        self.node_id = node_id
        self.state = "follower"
        self.term = 0
        self.voted_for = None

    async def start_election(self):
        self.state = "candidate"
        self.term += 1
        print(f"[{self.node_id}] Starting election (term {self.term})")

    async def become_leader(self):
        self.state = "leader"
        print(f"[{self.node_id}] Became leader")