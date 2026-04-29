import re
from aiohttp import web
from src.communication.failure_detector import FailureDetector
from src.consensus.raft import RaftNode
from src.nodes.cache_manager import CacheRoutesMixin, DistributedCacheManager
from src.nodes.lock_manager import DistributedLockManager, LockRoutesMixin
from src.nodes.queue_manager import DistributedQueueManager, QueueRoutesMixin
from src.utils.metrics import MetricsCollector


class BaseNode(CacheRoutesMixin, QueueRoutesMixin, LockRoutesMixin):
    def __init__(self, node_id, bind_host, port, peers=None, advertise_host=None, region="local", peer_regions=None, latency_profile=None):
        self.node_id = node_id
        self.bind_host = bind_host
        self.advertise_host = advertise_host or bind_host
        self.port = port
        self.peers = peers or []
        self.region = region
        self.peer_regions = peer_regions or {}
        self.latency_profile = latency_profile or {}
        self.failure_detector = FailureDetector(timeout_seconds=5.0, check_interval_seconds=1.0)
        self.metrics = MetricsCollector()
        for peer in self.peers:
            self.failure_detector.register_peer(peer)
        
        self.app = web.Application()
        self.app.add_routes([
            web.post('/message', self.handle_message),
            web.get('/openapi.json', self.openapi_json),
            web.get('/docs', self.swagger_docs),
            web.post('/lock/acquire', self.acquire_lock),
            web.post('/lock/release', self.release_lock),
            web.get('/lock/status', self.lock_status),
            web.get('/admin/locks/deadlocks', self.admin_deadlocks),
            web.post('/admin/locks/resolve', self.admin_resolve_deadlocks),
            web.post('/queue/enqueue', self.enqueue_queue),
            web.post('/queue/replicate', self.queue_replicate),
            web.post('/queue/dequeue', self.dequeue_queue),
            web.get('/queue/status', self.queue_status),
            web.post('/cache/set', self.cache_set),
            web.get('/cache/get', self.cache_get),
            web.post('/cache/delete', self.cache_delete),
            web.post('/cache/invalidate', self.cache_invalidate),
            web.get('/cache/status', self.cache_status),
            web.get('/metrics', self.metrics_status),
            web.get('/health', self.health_check)
        ])
        self.raft = RaftNode(self.node_id, self.peers, self.send_message, self.failure_detector)
        self.cache_manager = DistributedCacheManager()
        self.lock_manager = DistributedLockManager()
        self.advertise_addr = f"{self.advertise_host}:{self.port}"
        self.queue_manager = DistributedQueueManager(self.advertise_addr, self.peers)
        self.replication_tasks = set()

    def build_openapi_spec(self):
        base_url = f"http://{self.advertise_host}:{self.port}"
        return {
            "openapi": "3.0.3",
            "info": {
                "title": "Distributed Sync System API",
                "version": "1.0.0",
                "description": "HTTP API for Raft coordination, distributed locks, queueing, and cache coherence.",
            },
            "servers": [{"url": base_url}],
            "paths": {
                "/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {"200": {"description": "Node is alive"}},
                    }
                },
                "/message": {
                    "post": {
                        "summary": "Internal Raft message handler",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"200": {"description": "Message handled"}},
                    }
                },
                "/lock/acquire": {
                    "post": {
                        "summary": "Acquire a lock",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LockRequest"}}}},
                        "responses": {"200": {"description": "Lock granted"}, "409": {"description": "Lock is held"}},
                    }
                },
                "/lock/release": {
                    "post": {
                        "summary": "Release a lock",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LockRequest"}}}},
                        "responses": {"200": {"description": "Lock released"}, "409": {"description": "Release rejected"}},
                    }
                },
                "/lock/status": {
                    "get": {
                        "summary": "List current locks",
                        "responses": {"200": {"description": "Current lock table"}},
                    }
                },
                "/admin/locks/deadlocks": {
                    "get": {
                        "summary": "Inspect deadlocks",
                        "responses": {"200": {"description": "Deadlock graph"}},
                    }
                },
                "/admin/locks/resolve": {
                    "post": {
                        "summary": "Resolve deadlocks",
                        "requestBody": {"required": False, "content": {"application/json": {"schema": {"type": "object", "properties": {"strategy": {"type": "string"}}}}}},
                        "responses": {"200": {"description": "Deadlocks resolved"}},
                    }
                },
                "/queue/enqueue": {
                    "post": {
                        "summary": "Enqueue an item",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/QueueItem"}}}},
                        "responses": {"200": {"description": "Item enqueued"}},
                    }
                },
                "/queue/replicate": {
                    "post": {
                        "summary": "Replica endpoint for queue items",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"200": {"description": "Replica accepted"}},
                    }
                },
                "/queue/dequeue": {
                    "post": {
                        "summary": "Dequeue an item",
                        "requestBody": {"required": False, "content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"200": {"description": "Item dequeued"}, "404": {"description": "Queue empty"}},
                    }
                },
                "/queue/status": {
                    "get": {
                        "summary": "Inspect queue state",
                        "responses": {"200": {"description": "Queue snapshot"}},
                    }
                },
                "/cache/set": {
                    "post": {
                        "summary": "Write to cache",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CacheSetRequest"}}}},
                        "responses": {"200": {"description": "Cache updated"}},
                    }
                },
                "/cache/get": {
                    "get": {
                        "summary": "Read from cache",
                        "parameters": [{"name": "key", "in": "query", "required": True, "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "Cache hit"}, "404": {"description": "Cache miss"}},
                    }
                },
                "/cache/delete": {
                    "post": {
                        "summary": "Delete cache entry",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {"key": {"type": "string"}}}}}},
                        "responses": {"200": {"description": "Entry deleted"}},
                    }
                },
                "/cache/invalidate": {
                    "post": {
                        "summary": "Invalidate replicated cache entry",
                        "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"200": {"description": "Invalidation applied"}},
                    }
                },
                "/cache/status": {
                    "get": {
                        "summary": "Inspect cache state",
                        "responses": {"200": {"description": "Cache snapshot"}},
                    }
                },
            },
            "components": {
                "schemas": {
                    "LockRequest": {
                        "type": "object",
                        "required": ["resource"],
                        "properties": {
                            "resource": {"type": "string"},
                            "node_id": {"type": "string"},
                        },
                    },
                    "QueueItem": {
                        "type": "object",
                        "required": ["item"],
                        "properties": {
                            "item": {"type": ["string", "number", "object", "array", "boolean", "null"]},
                            "node_id": {"type": "string"},
                        },
                    },
                    "CacheSetRequest": {
                        "type": "object",
                        "required": ["key", "value"],
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": ["string", "number", "object", "array", "boolean", "null"]},
                            "node_id": {"type": "string"},
                        },
                    },
                }
            },
        }

    async def openapi_json(self, request):
        return web.json_response(self.build_openapi_spec())

    async def swagger_docs(self, request):
        html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Distributed Sync System API Docs</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\" />
  <style>body {{ margin: 0; background: #0f172a; }} #swagger-ui {{ margin: 0; }}</style>
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.onload = () => {{
      SwaggerUIBundle({{
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout',
      }});
    }};
  </script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")
        
    async def start_background_tasks(self, app):
        app.loop.create_task(self.raft.start())
        self.failure_detector.start_background_monitor()
        
    async def send_message(self, peer, message):
        return await self.post_json(peer, '/message', message)

    @staticmethod
    def _normalize_peer(peer):
        # On some Windows setups, resolving "localhost" in async client calls can
        # intermittently fail with network-name errors. Prefer loopback IPv4.
        if peer.startswith("localhost:"):
            return f"127.0.0.1:{peer.split(':', 1)[1]}"
        return peer

    async def post_json(self, peer, path, message):
        import aiohttp
        target_peer = self._normalize_peer(peer)
        url = f"http://{target_peer}{path}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=message) as resp:
                    self.metrics.record_peer_request("post", True)
                    return await resp.json()
            except Exception as e:
                self.metrics.record_peer_request("post", False)
                print(f"[{self.node_id}] Error sending to {target_peer}: {e}")

    async def get_json(self, peer, path, params=None):
        import aiohttp
        target_peer = self._normalize_peer(peer)
        url = f"http://{target_peer}{path}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    self.metrics.record_peer_request("get", True)
                    return await resp.json()
            except Exception as e:
                self.metrics.record_peer_request("get", False)
                print(f"[{self.node_id}] Error getting from {target_peer}: {e}")

    def leader_address(self):
        leader_id = self.raft.leader_id
        if not leader_id:
            return None

        if leader_id == self.node_id:
            return f"{self.advertise_host}:{self.port}"

        # Prefer explicit peer host match (works for docker service names).
        for peer in self.peers:
            host, _, _ = peer.partition(":")
            if host == leader_id:
                return peer

        match = re.search(r"(\d+)$", leader_id)
        if not match:
            return None

        expected_port = f"800{match.group(1)}"

        # Fallback: infer leader by conventional port mapping (works for localhost peers).
        for peer in self.peers:
            _, _, port = peer.rpartition(":")
            if port == expected_port:
                return peer

        return f"localhost:{expected_port}"

    def leader_state_payload(self):
        return {
            "leader_id": self.raft.leader_id,
            "term": self.raft.term,
            "state": self.raft.state,
        }

    async def forward_get_to_leader(self, path, params=None):
        leader_address = self.leader_address()
        if not leader_address:
            return web.json_response({
                "status": "error",
                "message": "leader belum diketahui",
                **self.leader_state_payload(),
            }, status=503)

        if leader_address == f"{self.advertise_host}:{self.port}":
            return None

        response = await self.get_json(leader_address, path, params=params)
        if response is None:
            return web.json_response({
                "status": "error",
                "message": "gagal terhubung ke leader",
                **self.leader_state_payload(),
            }, status=503)

        return web.json_response(response, status=200 if response.get("status") != "miss" else 404)

    async def read_json_body(self, request):
        try:
            return await request.json(), None
        except Exception:
            self.metrics.increment("request.invalid_json")
            return None, web.json_response({"status": "error", "message": "body harus JSON valid"}, status=400)

    async def forward_to_leader(self, path, payload):
        leader_address = self.leader_address()
        if not leader_address:
            return web.json_response({
                "status": "error",
                "message": "leader belum diketahui",
                **self.leader_state_payload(),
            }, status=503)

        if leader_address == f"{self.advertise_host}:{self.port}":
            return None

        response = await self.post_json(leader_address, path, payload)
        if response is None:
            return web.json_response({
                "status": "error",
                "message": "gagal terhubung ke leader",
                **self.leader_state_payload(),
            }, status=503)

        return web.json_response(response, status=200 if response.get("status") != "error" else 409)

    async def handle_message(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        msg_type = data.get("type")
        self.metrics.record_message(msg_type or "unknown")

        if msg_type == "vote_request":
            response = await self.raft.handle_vote_request(data)
            return web.json_response(response)

        elif msg_type == "vote_response":
            await self.raft.handle_vote_response(data)

        elif msg_type == "heartbeat":
            await self.raft.handle_heartbeat(data)

        return web.json_response({"status": "ok"})

    async def metrics_status(self, request):
        self.metrics.set_gauge("raft.state", self.raft.state)
        self.metrics.set_gauge("raft.leader_id", self.raft.leader_id)
        self.metrics.set_gauge("cache.size", self.cache_manager.stats().get("size", 0))
        self.metrics.set_gauge("queue.size", self.queue_manager.size())
        self.metrics.set_gauge("failure_detector.suspected", self.failure_detector.suspected_peers())

        return web.json_response({
            "status": "ok",
            "node": self.node_id,
            "metrics": self.metrics.snapshot(),
        })

    async def health_check(self, request):
        self.metrics.record_request("/health", 200)
        return web.json_response({
            "node": self.node_id,
            "leader_id": self.raft.leader_id,
            "suspected_peers": self.failure_detector.suspected_peers(),
        })

    def run(self):
        async def on_startup(app):
            import asyncio
            asyncio.create_task(self.raft.start())
            self.failure_detector.start_background_monitor()

        self.app.on_startup.append(on_startup)

        print(f"Node {self.node_id} running at {self.bind_host}:{self.port}")
        web.run_app(self.app, host=self.bind_host, port=self.port)
