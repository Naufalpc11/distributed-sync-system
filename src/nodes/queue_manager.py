import hashlib
import os
import sqlite3
import threading
from pathlib import Path
from bisect import bisect
import asyncio

from aiohttp import web


class ConsistentHashRing:
    def __init__(self, nodes=None, replicas=3):
        self.replicas = replicas
        self.ring = []
        self._keys = []
        self.nodes = set()
        if nodes:
            for n in nodes:
                self.add_node(n)

    def _hash(self, key):
        h = hashlib.md5(key.encode()).hexdigest()
        return int(h, 16)

    def add_node(self, node):
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.replicas):
            k = self._hash(f"{node}#{i}")
            self._keys.append((k, node))
        self._keys.sort()

    def get_node(self, key):
        if not self._keys:
            return None
        k = self._hash(key)
        keys = [x[0] for x in self._keys]
        idx = bisect(keys, k) % len(self._keys)
        return self._keys[idx][1]


class DistributedQueueManager:
    def __init__(self, node_addr=None, peers=None, db_dir="data"):
        # backward-compatible: if node_addr not provided, use a temporary DB
        import tempfile
        if node_addr is None:
            self.node_addr = "local"
            tmp = tempfile.NamedTemporaryFile(prefix="queue_local_", suffix=".db", delete=False)
            self.db_path = tmp.name
            tmp.close()
            in_memory = False
        else:
            self.node_addr = node_addr
            in_memory = False
        self.peers = peers or []
        self.ring = ConsistentHashRing(nodes=[self.node_addr] + list(self.peers))
        self.lock = threading.Lock()

        # DB persistence
        if not hasattr(self, 'db_path'):
            Path(db_dir).mkdir(parents=True, exist_ok=True)
            safe = self.node_addr.replace(':', '_')
            self.db_path = os.path.join(db_dir, f"queue_{safe}.db")
        self._init_db()
        self.queue = self._load_from_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                node_id TEXT,
                enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replicated_count INTEGER DEFAULT 0,
                pending_peers TEXT DEFAULT ''
            )
            """)
            conn.commit()

    def _load_from_db(self):
        res = []
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, item, node_id FROM queue ORDER BY id ASC")
            for row in cur.fetchall():
                res.append({"id": row[0], "item": row[1], "node_id": row[2]})
        return res

    def owner_for(self, item):
        n = self.ring.get_node(str(item))
        return n or self.node_addr

    def enqueue(self, item, node_id):
        if item is None:
            return False

        owner = self.owner_for(item)
        if owner != self.node_addr:
            # not local owner
            return False

        # prepare pending_peers metadata for replication
        pending = ','.join([p for p in self.peers if p != self.node_addr])
        replicated_count = 0 if pending else 1
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO queue (item, node_id, replicated_count, pending_peers) VALUES (?, ?, ?, ?)", (str(item), node_id, replicated_count, pending))
                conn.commit()
                rowid = cur.lastrowid
                self.queue.append({"id": rowid, "item": str(item), "node_id": node_id, "replicated_count": replicated_count, "pending_peers": pending})
        return True

    def mark_replica_ack(self, msg_id, peer):
        """Mark that peer has acknowledged replication for message id."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT pending_peers, replicated_count FROM queue WHERE id = ?", (msg_id,))
                row = cur.fetchone()
                if not row:
                    return False
                pending, replicated = row[0], row[1]
                pending_list = [p for p in pending.split(',') if p]
                if peer in pending_list:
                    pending_list.remove(peer)
                    replicated = replicated + 1
                    new_pending = ','.join(pending_list)
                    cur.execute("UPDATE queue SET pending_peers = ?, replicated_count = ? WHERE id = ?", (new_pending, replicated, msg_id))
                    conn.commit()
                    # update in-memory queue
                    for e in self.queue:
                        if e.get('id') == msg_id:
                            e['replicated_count'] = replicated
                            e['pending_peers'] = new_pending
                    return True
                return False

    def list_pending(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, item, node_id, replicated_count, pending_peers FROM queue ORDER BY id ASC")
            return [dict(id=r[0], item=r[1], node_id=r[2], replicated_count=r[3], pending_peers=r[4]) for r in cur.fetchall()]

    def force_enqueue(self, item, node_id):
        """Force enqueue locally regardless of ring ownership. Used as fallback."""
        if item is None:
            return False
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO queue (item, node_id) VALUES (?, ?)", (str(item), node_id))
                conn.commit()
                rowid = cur.lastrowid
                self.queue.append({"id": rowid, "item": str(item), "node_id": node_id})
        return True

    def dequeue(self):
        with self.lock:
            if not self.queue:
                return None
            entry = self.queue.pop(0)
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM queue WHERE id = ?", (entry["id"],))
                conn.commit()
            return entry

    def peek(self):
        with self.lock:
            if not self.queue:
                return None
            return self.queue[0]

    def list_queue(self):
        with self.lock:
            return list(self.queue)

    def size(self):
        with self.lock:
            return len(self.queue)


class QueueRoutesMixin:
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

        owner = self.queue_manager.owner_for(item)
        if owner != self.advertise_addr:
            payload = {"item": item, "node_id": requester}
            response = await self.post_json(owner, "/queue/enqueue", payload)
            if response is None:
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

        self.queue_manager.force_enqueue(item, node_id)

        return web.json_response({"status": "ok", "id": msg_id})
