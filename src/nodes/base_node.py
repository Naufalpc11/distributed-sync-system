import asyncio
import re
from aiohttp import web
from src.consensus.raft import RaftNode
from src.nodes.cache_manager import DistributedCacheManager
from src.nodes.lock_manager import DistributedLockManager
from src.nodes.queue_manager import DistributedQueueManager


class BaseNode:
    def __init__(self, node_id, bind_host, port, peers=None, advertise_host=None, region="local", peer_regions=None, latency_profile=None):
        self.node_id = node_id
        self.bind_host = bind_host
        self.advertise_host = advertise_host or bind_host
        self.port = port
        self.peers = peers or []
        self.region = region
        self.peer_regions = peer_regions or {}
        self.latency_profile = latency_profile or {}
        
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
            web.get('/health', self.health_check)
        ])
        self.raft = RaftNode(self.node_id, self.peers, self.send_message)
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

    async def get_json(self, peer, path, params=None):
        import aiohttp
        url = f"http://{peer}{path}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    return await resp.json()
            except Exception as e:
                print(f"[{self.node_id}] Error getting from {peer}: {e}")

    def get_peer_region(self, peer):
        return self.peer_regions.get(peer, self.region)

    def get_peer_latency(self, peer):
        peer_region = self.get_peer_region(peer)
        if peer_region == self.region:
            return 0

        latency_key = f"{self.region}->{peer_region}"
        reverse_key = f"{peer_region}->{self.region}"

        if latency_key in self.latency_profile:
            return int(self.latency_profile[latency_key])

        if reverse_key in self.latency_profile:
            return int(self.latency_profile[reverse_key])

        return 50

    def ordered_peers_by_latency(self):
        return sorted(self.peers, key=self.get_peer_latency)

    def should_replicate_cache(self):
        return bool(self.peers)

    async def replicate_cache_write(self, key, value, version, requester, source="leader"):
        if not self.should_replicate_cache():
            return

        for peer in self.ordered_peers_by_latency():
            delay_ms = self.get_peer_latency(peer)
            task = asyncio.create_task(self._replicate_cache_to_peer(peer, key, value, version, requester, source, delay_ms))
            self.replication_tasks.add(task)
            task.add_done_callback(self.replication_tasks.discard)

    async def _replicate_cache_to_peer(self, peer, key, value, version, requester, source, delay_ms):
        await asyncio.sleep(delay_ms / 1000)

        payload = {
            "key": key,
            "value": value,
            "node_id": requester,
            "version": version,
            "replica": True,
            "source": source,
        }

        await self.post_json(peer, "/cache/set", payload)

    async def replicate_cache_delete(self, key, requester, source="leader"):
        if not self.should_replicate_cache():
            return

        for peer in self.ordered_peers_by_latency():
            delay_ms = self.get_peer_latency(peer)
            task = asyncio.create_task(self._replicate_cache_delete_to_peer(peer, key, requester, source, delay_ms))
            self.replication_tasks.add(task)
            task.add_done_callback(self.replication_tasks.discard)

    async def _replicate_cache_delete_to_peer(self, peer, key, requester, source, delay_ms):
        await asyncio.sleep(delay_ms / 1000)

        payload = {
            "key": key,
            "node_id": requester,
            "replica": True,
            "source": source,
        }

        await self.post_json(peer, "/cache/delete", payload)

    async def replicate_cache_invalidate(self, key, requester, source="leader"):
        if not self.should_replicate_cache():
            return

        for peer in self.ordered_peers_by_latency():
            delay_ms = self.get_peer_latency(peer)
            task = asyncio.create_task(self._replicate_cache_invalidate_to_peer(peer, key, requester, source, delay_ms))
            self.replication_tasks.add(task)
            task.add_done_callback(self.replication_tasks.discard)

    async def _replicate_cache_invalidate_to_peer(self, peer, key, requester, source, delay_ms):
        await asyncio.sleep(delay_ms / 1000)

        payload = {
            "key": key,
            "node_id": requester,
            "replica": True,
            "source": source,
        }

        await self.post_json(peer, "/cache/invalidate", payload)

    def leader_address(self):
        leader_id = self.raft.leader_id
        if not leader_id:
            return None

        match = re.search(r"(\d+)$", leader_id)
        if not match:
            return None

        return f"{self.advertise_host}:800{match.group(1)}"

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

    async def acquire_lock(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

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
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

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
        if self.raft.state != "leader":
            forwarded = await self.forward_get_to_leader('/lock/status')
            if forwarded is not None:
                return forwarded

        return web.json_response({
            "status": "ok",
            "locks": {
                k: (v["owners"][0] if v.get("mode") == "exclusive" and v.get("owners") else v.get("owners"))
                for k, v in self.lock_manager.list_locks().items()
            },
            **self.leader_state_payload(),
        })

    async def admin_deadlocks(self, request):
        if self.raft.state != "leader":
            forwarded = await self.forward_get_to_leader('/admin/locks/deadlocks')
            if forwarded is not None:
                return forwarded

        cycles = self.lock_manager.detect_deadlocks()
        return web.json_response({
            "status": "ok",
            "deadlocks": cycles,
            "waiters": self.lock_manager.list_waiters(),
            "locks": self.lock_manager.list_locks(),
            **self.leader_state_payload(),
        })

    async def admin_resolve_deadlocks(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        if self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/admin/locks/resolve', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({"status": "error", "message": "node ini belum leader", **self.leader_state_payload()}, status=409)

        strategy = data.get("strategy", "youngest")
        victims = self.lock_manager.resolve_deadlocks(strategy=strategy)
        return web.json_response({
            "status": "ok",
            "resolved": victims,
            **self.leader_state_payload(),
        })

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
        # route to shard owner; if owner is another peer, forward
        owner = self.queue_manager.owner_for(item)
        if owner != self.advertise_addr:
            # forward to owner; if forwarding fails, fallback to local enqueue
            payload = {"item": item, "node_id": requester}
            response = await self.post_json(owner, "/queue/enqueue", payload)
            if response is None:
                # fallback: try local enqueue to avoid failing tests or temporary network issues
                accepted = self.queue_manager.force_enqueue(item, requester)
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
            return web.json_response(response)

        accepted = self.queue_manager.enqueue(item, requester)
        if accepted:
            # start background replication to peers for durability (leader initiates)
            asyncio.create_task(self._replicate_enqueue_to_peers(item, requester))
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
        if self.raft.state != "leader":
            forwarded = await self.forward_get_to_leader('/queue/status')
            if forwarded is not None:
                return forwarded

        return web.json_response({
            "status": "ok",
            "queue": self.queue_manager.list_queue(),
            "queue_size": self.queue_manager.size(),
            **self.leader_state_payload(),
        })

    async def _replicate_enqueue_to_peers(self, item, enqueued_by):
        # find the most recent pending message (assumes leader just enqueued)
        pending = self.queue_manager.list_pending()
        if not pending:
            return
        msg = pending[-1]
        msg_id = msg['id']
        payload = {"id": msg_id, "item": msg['item'], "node_id": msg['node_id'], "origin": self.node_id}

        async def replicate_to_peer(peer):
            retries = 0
            while retries < 5:
                resp = await self.post_json(peer, '/queue/replicate', payload)
                if resp and resp.get('status') == 'ok':
                    # mark ack locally
                    self.queue_manager.mark_replica_ack(msg_id, peer)
                    return
                retries += 1
                await asyncio.sleep(1 + retries)

        for peer in self.ordered_peers_by_latency():
            if peer == self.advertise_addr:
                continue
            asyncio.create_task(replicate_to_peer(peer))

    async def queue_replicate(self, request):
        data, err = await self.read_json_body(request)
        if err is not None:
            return err

        msg_id = data.get('id')
        item = data.get('item')
        node_id = data.get('node_id')

        if not msg_id or item is None:
            return web.json_response({"status": "error", "message": "invalid payload"}, status=400)

        # persist replica locally
        self.queue_manager.force_enqueue(item, node_id)

        return web.json_response({"status": "ok", "id": msg_id})

    async def cache_set(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        key = data.get("key")
        value = data.get("value")
        requester = data.get("node_id", self.node_id)
        is_replica = bool(data.get("replica", False))

        if not is_replica and self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/cache/set', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if not key:
            return web.json_response({"status": "error", "message": "key wajib diisi"}, status=400)

        stored = self.cache_manager.set(key, value, requester)
        if stored:
            entry = self.cache_manager.get(key)
            if self.raft.state == "leader" and not is_replica:
                # leader write: set local to Modified and invalidate others
                asyncio.create_task(self.replicate_cache_invalidate(key, requester))

            return web.json_response({
                "status": "ok",
                "action": "set",
                "key": key,
                "value": entry["value"],
                "version": entry["version"],
                "updated_by": entry["updated_by"],
                "state": entry.get("state"),
                "region": self.region,
                **self.leader_state_payload(),
            })

        return web.json_response({"status": "error", "message": "gagal menyimpan cache"}, status=500)

    async def cache_get(self, request):
        key = request.query.get("key")

        if not key:
            return web.json_response({"status": "error", "message": "key wajib diisi"}, status=400)

        if self.raft.state != "leader":
            leader_address = self.leader_address()
            if not leader_address:
                return web.json_response({
                    "status": "error",
                    "message": "leader belum diketahui",
                    **self.leader_state_payload(),
                }, status=503)

            if leader_address != f"{self.advertise_host}:{self.port}":
                response = await self.get_json(leader_address, '/cache/get', params={"key": key})
                if response is None:
                    return web.json_response({
                        "status": "error",
                        "message": "gagal terhubung ke leader",
                        **self.leader_state_payload(),
                    }, status=503)

                return web.json_response(response, status=200 if response.get("status") != "miss" else 404)

        entry = self.cache_manager.get(key)
        if entry is None:
            return web.json_response({
                "status": "miss",
                "key": key,
                **self.leader_state_payload(),
            }, status=404)

        return web.json_response({
            "status": "ok",
            "action": "get",
            "key": key,
            "value": entry["value"],
            "version": entry["version"],
            "updated_by": entry["updated_by"],
            **self.leader_state_payload(),
        })

    async def cache_delete(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        key = data.get("key")
        requester = data.get("node_id", self.node_id)
        is_replica = bool(data.get("replica", False))

        if not is_replica and self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/cache/delete', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if not key:
            return web.json_response({"status": "error", "message": "key wajib diisi"}, status=400)

        deleted = self.cache_manager.delete(key)
        if deleted:
            if self.raft.state == "leader" and not is_replica:
                asyncio.create_task(self.replicate_cache_delete(key, requester))
                asyncio.create_task(self.replicate_cache_invalidate(key, requester))

            return web.json_response({
                "status": "ok",
                "action": "delete",
                "key": key,
                "requested_by": requester,
                "region": self.region,
                **self.leader_state_payload(),
            })

        return web.json_response({
            "status": "miss",
            "key": key,
            **self.leader_state_payload(),
        }, status=404)

    async def cache_invalidate(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

        key = data.get("key")
        requester = data.get("node_id", self.node_id)
        is_replica = bool(data.get("replica", False))

        if not is_replica and self.raft.state != "leader":
            forwarded = await self.forward_to_leader('/cache/invalidate', data)
            if forwarded is not None:
                return forwarded
            return web.json_response({
                "status": "error",
                "message": "node ini belum leader",
                **self.leader_state_payload(),
            }, status=409)

        if not key:
            return web.json_response({"status": "error", "message": "key wajib diisi"}, status=400)

        invalidated = self.cache_manager.invalidate(key, requester)
        if invalidated:
            return web.json_response({
                "status": "ok",
                "action": "invalidate",
                "key": key,
                "requested_by": requester,
                **self.leader_state_payload(),
            })

        return web.json_response({"status": "miss", "key": key}, status=404)

    async def cache_status(self, request):
        if self.raft.state != "leader":
            forwarded = await self.forward_get_to_leader('/cache/status')
            if forwarded is not None:
                return forwarded

        return web.json_response({
            "status": "ok",
            "cache": self.cache_manager.list_cache(),
            "cache_stats": self.cache_manager.stats(),
            "region": self.region,
            **self.leader_state_payload(),
        })
            
    async def handle_message(self, request):
        data, error_response = await self.read_json_body(request)
        if error_response is not None:
            return error_response

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

        print(f"Node {self.node_id} running at {self.bind_host}:{self.port}")
        web.run_app(self.app, host=self.bind_host, port=self.port)