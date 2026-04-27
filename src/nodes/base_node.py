import asyncio
import re
from aiohttp import web
from src.consensus.raft import RaftNode
from src.nodes.lock_manager import DistributedLockManager
<<<<<<< HEAD
from src.nodes.queue_manager import DistributedQueueManager
=======
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03


class BaseNode:
    def __init__(self, node_id, host, port, peers=None):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers = peers or []
        
        self.app = web.Application()
        self.app.add_routes([
            web.post('/message', self.handle_message),
            web.post('/lock/acquire', self.acquire_lock),
            web.post('/lock/release', self.release_lock),
            web.get('/lock/status', self.lock_status),
<<<<<<< HEAD
            web.post('/queue/enqueue', self.enqueue_queue),
            web.post('/queue/dequeue', self.dequeue_queue),
            web.get('/queue/status', self.queue_status),
=======
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
            web.get('/health', self.health_check)
        ])
        self.raft = RaftNode(self.node_id, self.peers, self.send_message)
        self.lock_manager = DistributedLockManager()
<<<<<<< HEAD
        self.queue_manager = DistributedQueueManager()
=======
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
        
    async def start_background_tasks(self, app):
        app.loop.create_task(self.raft.start())
        
    async def send_message(self, peer, message):
        return await self.post_json(peer, '/message', message)

    async def post_json(self, peer, path, message):
        import aiohttp
        url = f"http://{peer}{path}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=message) as resp:
                    return await resp.json()
            except Exception as e:
                print(f"[{self.node_id}] Error sending to {peer}: {e}")

    def leader_address(self):
        leader_id = self.raft.leader_id
        if not leader_id:
            return None

        match = re.search(r"(\d+)$", leader_id)
        if not match:
            return None

<<<<<<< HEAD
        return f"{self.host}:800{match.group(1)}"
=======
        return f"{self.host}:80{match.group(1)}"
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03

    def leader_state_payload(self):
        return {
            "leader_id": self.raft.leader_id,
            "term": self.raft.term,
            "state": self.raft.state,
        }

<<<<<<< HEAD
    async def read_json_body(self, request):
        try:
            return await request.json(), None
        except Exception:
            return None, web.json_response({"status": "error", "message": "body harus JSON valid"}, status=400)

=======
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
    async def forward_to_leader(self, path, payload):
        leader_address = self.leader_address()
        if not leader_address:
            return web.json_response({
                "status": "error",
                "message": "leader belum diketahui",
                **self.leader_state_payload(),
            }, status=503)

        if leader_address == f"{self.host}:{self.port}":
            return None

        response = await self.post_json(leader_address, path, payload)
        if response is None:
            return web.json_response({
                "status": "error",
                "message": "gagal terhubung ke leader",
                **self.leader_state_payload(),
            }, status=503)

        return web.json_response(response, status=200 if response.get("status") != "error" else 409)

    async def acquire_lock(self, request):
<<<<<<< HEAD
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

=======
        data = await request.json()
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
        resource = data.get("resource")
        requester = data.get("node_id", self.node_id)

        if self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/lock/acquire', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if not resource:
            return web.json_response({"status": "error", "message": "resource wajib diisi"}, status=400)

        granted = self.lock_manager.acquire_lock(resource, requester)
        if granted:
            return web.json_response({
                "status": "ok",
                "action": "acquire",
                "resource": resource,
                "owner": requester,
                **self.leader_state_payload(),
            })

        return web.json_response({
            "status": "locked",
            "resource": resource,
            "owner": self.lock_manager.get_owner(resource),
            **self.leader_state_payload(),
        }, status=409)

    async def release_lock(self, request):
<<<<<<< HEAD
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

=======
        data = await request.json()
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
        resource = data.get("resource")
        requester = data.get("node_id", self.node_id)

        if self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/lock/release', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if not resource:
            return web.json_response({"status": "error", "message": "resource wajib diisi"}, status=400)

        released = self.lock_manager.release_lock(resource, requester)
        if released:
            return web.json_response({
                "status": "ok",
                "action": "release",
                "resource": resource,
                "owner": requester,
                **self.leader_state_payload(),
            })

        return web.json_response({
            "status": "error",
            "message": "lock tidak dimiliki node ini atau belum ada",
            "resource": resource,
            "owner": self.lock_manager.get_owner(resource),
            **self.leader_state_payload(),
        }, status=409)

    async def lock_status(self, request):
        return web.json_response({
            "status": "ok",
            "locks": self.lock_manager.list_locks(),
            **self.leader_state_payload(),
        })
<<<<<<< HEAD

    async def enqueue_queue(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        item = data.get("item")
        requester = data.get("node_id", self.node_id)

        if self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/queue/enqueue', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if item is None:
            return web.json_response({"status": "error", "message": "item wajib diisi"}, status=400)

        accepted = self.queue_manager.enqueue(item, requester)
        if accepted:
            return web.json_response({
                "status": "ok",
                "action": "enqueue",
                "item": item,
                "requested_by": requester,
                "queue_size": self.queue_manager.size(),
                **self.leader_state_payload(),
            })

        return web.json_response({"status": "error", "message": "gagal enqueue"}, status=500)

    async def dequeue_queue(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        requester = data.get("node_id", self.node_id)

        if self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/queue/dequeue', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        item = self.queue_manager.dequeue()
        if item is None:
            return web.json_response({
                "status": "empty",
                "message": "queue kosong",
                "requested_by": requester,
                **self.leader_state_payload(),
            }, status=404)

        return web.json_response({
            "status": "ok",
            "action": "dequeue",
            "item": item["item"],
            "enqueued_by": item["node_id"],
            "requested_by": requester,
            "queue_size": self.queue_manager.size(),
            **self.leader_state_payload(),
        })

    async def queue_status(self, request):
        return web.json_response({
            "status": "ok",
            "queue": self.queue_manager.list_queue(),
            "queue_size": self.queue_manager.size(),
            **self.leader_state_payload(),
        })
            
    async def handle_message(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

=======
            
    async def handle_message(self, request):
        data = await request.json()
>>>>>>> cbb638edcfac6f4708b37efd8ca3123e186d3c03
        msg_type = data.get("type")

        if msg_type == "vote_request":
            response = await self.raft.handle_vote_request(data)
            return web.json_response(response)

        elif msg_type == "vote_response":
            await self.raft.handle_vote_response(data)

        elif msg_type == "heartbeat":
            await self.raft.handle_heartbeat(data)

        return web.json_response({"status": "ok"})

    async def health_check(self, request):
        return web.json_response({"node": self.node_id})

    def run(self):
        async def on_startup(app):
            import asyncio
            asyncio.create_task(self.raft.start())

        self.app.on_startup.append(on_startup)

        print(f"Node {self.node_id} running at {self.host}:{self.port}")
        web.run_app(self.app, host=self.host, port=self.port)