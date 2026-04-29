from collections import OrderedDict
import asyncio
import time
from aiohttp import web


class DistributedCacheManager:
    """MESI-like cache manager (local node view).

    Each entry: {
        'value': ..., 'version': int, 'updated_by': node_id,
        'state': 'M'|'E'|'S'|'I', 'last_access': timestamp
    }

    This is a local cache; invalidation messages from other nodes set entries to 'I'.
    LRU eviction enforced by `capacity`.
    """

    def __init__(self, capacity=100):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0

    def _touch(self, key):
        # move to end for LRU
        if key in self.cache:
            entry = self.cache.pop(key)
            entry['last_access'] = time.time()
            self.cache[key] = entry

    def _evict_if_needed(self):
        while len(self.cache) > self.capacity:
            # pop oldest
            self.cache.popitem(last=False)

    def set(self, key, value, node_id, mode='local'):
        """Local write: mode='local' for writer, mode='replica' when applying replica push.

        Writer should set state to M (modified). Replica writes can set to S (shared).
        """
        if not key:
            return False

        current = self.cache.get(key)
        version = 1 if current is None else current['version'] + 1
        state = 'S' if mode == 'replica' else 'M'
        entry = {
            'value': value,
            'version': version,
            'updated_by': node_id,
            'state': state,
            'last_access': time.time(),
        }
        # store with LRU semantics
        if key in self.cache:
            self.cache.pop(key)
        self.cache[key] = entry
        self._evict_if_needed()
        return True

    def get(self, key):
        entry = self.cache.get(key)
        if entry is None or entry.get('state') == 'I':
            self.misses += 1
            return None
        self.hits += 1
        self._touch(key)
        return entry

    def invalidate(self, key, requester=None):
        """Invalidate a key (set to I) due to remote write by requester."""
        entry = self.cache.get(key)
        if not entry:
            return False
        entry['state'] = 'I'
        entry['last_access'] = time.time()
        # keep tombstone meta
        self.cache[key] = entry
        return True

    def delete(self, key):
        if key not in self.cache:
            return False

        del self.cache[key]
        return True

    def list_cache(self):
        # return JSON-serializable view
        return {k: {**v, 'last_access': v.get('last_access')} for k, v in self.cache.items()}

    def clear(self):
        self.cache.clear()

    def stats(self):
        return {'hits': self.hits, 'misses': self.misses, 'size': len(self.cache)}


class CacheRoutesMixin:
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
