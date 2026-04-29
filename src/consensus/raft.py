import asyncio
import random
import time

from src.communication.failure_detector import FailureDetector

class RaftNode:
    def __init__(self, node_id, peers, send_func, failure_detector=None):
        self.node_id = node_id
        self.peers = peers
        self.send = send_func
        self.failure_detector = failure_detector or FailureDetector()

        for peer in self.peers:
            self.failure_detector.register_peer(peer)

        self.state = "follower"
        self.term = 0
        self.voted_for = None

        self.votes = 0
        self.leader_id = None

        self.reset_timeout()
        self.last_heartbeat = time.time()

    async def start(self):
        print(f"[{self.node_id}] Raft started")  # 👈 TAMBAHIN INI

        while True:
            await asyncio.sleep(1)

            if self.state != "leader":
                if time.time() - self.last_heartbeat > self.election_timeout:
                    await self.start_election()

            if self.state == "leader":
                await self.send_heartbeat()
                
    def reset_timeout(self):
        self.election_timeout = random.uniform(3, 6)
        self.last_heartbeat = time.time()
        
    async def start_election(self):
        self.state = "candidate"
        self.term += 1
        self.voted_for = self.node_id
        self.votes = 1

        self.reset_timeout()  # 🔥 penting

        print(f"[{self.node_id}] Start election (term {self.term})")

        for peer in self.peers:
            response = await self.send(peer, {
                "type": "vote_request",
                "term": self.term,
                "candidate_id": self.node_id
            })

            if response and response.get("type") == "vote_response":
                await self.handle_vote_response(response)

    async def handle_vote_request(self, msg):
        if msg["term"] > self.term:
            self.term = msg["term"]
            self.voted_for = None
            self.state = "follower"

        vote_granted = False

        if msg["term"] == self.term and self.voted_for in [None, msg["candidate_id"]]:
            vote_granted = True
            self.voted_for = msg["candidate_id"]
            print(f"[{self.node_id}] Vote granted to {msg['candidate_id']} (term {self.term})")

        response = {
            "type": "vote_response",
            "vote_granted": vote_granted,
            "term": self.term
        }

        sender = msg.get("sender")
        if sender:
            await self.send(sender, response)

        return response
        
    async def handle_vote_response(self, msg):
        if self.state != "candidate":
            return

        if msg["vote_granted"]:
            self.votes += 1

        if self.votes > (len(self.peers) + 1) // 2:
            self.state = "leader"
            self.leader_id = self.node_id
            if hasattr(self.failure_detector, "record_leader_change"):
                self.failure_detector.record_leader_change(self.leader_id)
            print(f"[{self.node_id}] Became LEADER")

    async def send_heartbeat(self):
        for peer in self.peers:
            response = await self.send(peer, {
                "type": "heartbeat",
                "leader_id": self.node_id,
                "term": self.term
            })

            if response is None:
                self.failure_detector.mark_failed(peer)
            else:
                self.failure_detector.record_contact(peer)

    async def handle_heartbeat(self, msg):
        self.leader_id = msg["leader_id"]
        self.last_heartbeat = time.time()
        self.failure_detector.record_heartbeat(msg["leader_id"])

        if msg["term"] >= self.term:
            self.state = "follower"
            self.term = msg["term"]
            print(f"[{self.node_id}] Heartbeat from leader {self.leader_id} (term {self.term})")

        self.reset_timeout()
    
    async def handle_message(self, request):
        data = await request.json()
        msg_type = data.get("type")

        if msg_type == "vote_request":
            response = await self.raft.handle_vote_request(data)
            return web.json_response(response)

        elif msg_type == "vote_response":
            await self.raft.handle_vote_response(data)

        elif msg_type == "heartbeat":
            await self.raft.handle_heartbeat(data)

        return web.json_response({"status": "ok"})