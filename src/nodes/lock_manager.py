from aiohttp import web


class DistributedLockManager:
    def __init__(self):
        # resource -> owner node_id
        self.locks = {}
        # resource -> list of waiting node_ids (FIFO)
        self.waiting = {}

    def acquire_lock(self, resource, node_id, mode="exclusive"):
        """Backward-compatible wrapper: boolean API. Default mode=exclusive."""
        granted, _ = self.acquire_lock_with_info(resource, node_id, mode=mode)
        return bool(granted)

    def acquire_lock_with_info(self, resource, node_id, mode="exclusive"):
        """Rich acquire API returning (granted, promoted_owner).

        mode: 'exclusive' or 'shared'
        """
        mode = mode or "exclusive"
        if not resource:
            return False, None

        info = self.locks.get(resource)
        # not locked: grant
        if info is None:
            if mode == "shared":
                self.locks[resource] = {"mode": "shared", "owners": {node_id}}
            else:
                self.locks[resource] = {"mode": "exclusive", "owners": {node_id}}
            return True, None

        # locked
        cur_mode = info.get("mode")
        owners = info.get("owners", set())

        # already owner
        if node_id in owners:
            # if current mode is shared and request exclusive, upgrade not allowed automatically
            return True, None

        # shared current
        if cur_mode == "shared":
            if mode == "shared":
                owners.add(node_id)
                info["owners"] = owners
                self.locks[resource] = info
                return True, None
            # requesting exclusive while shared owners exist -> wait
            q = self.waiting.setdefault(resource, [])
            entry = {"node_id": node_id, "mode": mode}
            if all(w["node_id"] != node_id for w in q):
                q.append(entry)
            return False, None

        # exclusive current: cannot grant unless same owner
        if cur_mode == "exclusive":
            q = self.waiting.setdefault(resource, [])
            entry = {"node_id": node_id, "mode": mode}
            if all(w["node_id"] != node_id for w in q):
                q.append(entry)
            return False, None

    def release_lock(self, resource, node_id):
        """Backward-compatible wrapper: boolean API."""
        ok, _ = self.release_lock_with_info(resource, node_id)
        return bool(ok)

    def release_lock_with_info(self, resource, node_id):
        """Rich release API returning (ok, promoted_owners).

        promoted_owners: list of node_ids promoted (if any) due to victim removal.
        """
        info = self.locks.get(resource)
        # not locked
        if info is None:
            # if node was waiting, remove it
            q = self.waiting.get(resource)
            if q:
                q2 = [w for w in q if w.get("node_id") != node_id]
                if q2:
                    self.waiting[resource] = q2
                else:
                    self.waiting.pop(resource, None)
            return False, None

        owners = info.get("owners", set())
        if node_id not in owners:
            # if node was waiting, remove from queue
            q = self.waiting.get(resource)
            if q:
                q2 = [w for w in q if w.get("node_id") != node_id]
                if q2:
                    self.waiting[resource] = q2
                else:
                    self.waiting.pop(resource, None)
            return False, None

        # remove from owners
        owners.discard(node_id)
        if owners:
            info["owners"] = owners
            self.locks[resource] = info
            return True, None

        # no more owners: clear lock entry
        self.locks.pop(resource, None)
        # per backward compatibility, do not auto-promote waiting nodes here
        return True, None

    def get_owner(self, resource):
        info = self.locks.get(resource)
        if not info:
            return None
        owners = info.get("owners", set())
        if info.get("mode") == "exclusive":
            # return single owner for backward compatibility
            return next(iter(owners)) if owners else None
        # shared: return list
        return list(owners)

    def is_locked(self, resource):
        return resource in self.locks

    def list_locks(self):
        # return JSON-serializable view
        out = {}
        for r, info in self.locks.items():
            out[r] = {"mode": info.get("mode"), "owners": list(info.get("owners", []))}
        return out

    def list_waiters(self):
        return {r: list(q) for r, q in self.waiting.items()}

    def detect_deadlocks(self):
        """Detect cycles in the wait-for graph and return list of cycles.

        Each cycle is a list of node_ids forming the cycle.
        """
        # Build wait-for graph: waiting_node -> set(owner_node_ids)
        graph = {}
        for resource, waiters in self.waiting.items():
            owner_info = self.locks.get(resource)
            if not owner_info:
                continue
            owner_nodes = set(owner_info.get("owners", []))
            for waiter in waiters:
                wid = waiter.get("node_id") if isinstance(waiter, dict) else waiter
                if not wid:
                    continue
                graph.setdefault(wid, set()).update(owner_nodes)

        # detect cycles using DFS
        visited = {}
        cycles = []

        def dfs(u, stack):
            visited[u] = 1
            stack.append(u)
            for v in graph.get(u, ()):  # neighbors
                if visited.get(v) == 1:
                    # found cycle: slice stack
                    try:
                        idx = stack.index(v)
                        cycles.append(stack[idx:].copy())
                    except ValueError:
                        cycles.append([v, u])
                elif visited.get(v) is None:
                    dfs(v, stack)
            stack.pop()
            visited[u] = 2

        for node in list(graph.keys()):
            if visited.get(node) is None:
                dfs(node, [])

        return cycles

    def resolve_deadlocks(self, strategy="youngest"):
        """Resolve detected deadlocks by selecting a victim in each cycle.

        strategy: 'youngest' (max node_id if numeric), 'oldest' (min), or 'random'.
        Returns list of victims that were chosen and released.
        """
        import random

        cycles = self.detect_deadlocks()
        victims = []
        for cycle in cycles:
            if not cycle:
                continue
            # pick victim
            def keyfn(x):
                try:
                    return int(x)
                except Exception:
                    return x

            if strategy == "youngest":
                victim = max(cycle, key=keyfn)
            elif strategy == "oldest":
                victim = min(cycle, key=keyfn)
            else:
                victim = random.choice(cycle)

            # force release all locks owned by victim
            released = []
            for r, owner in list(self.locks.items()):
                info = owner
                owners = set(info.get("owners", []))
                if victim in owners:
                    # remove victim from owners
                    owners.discard(victim)
                    if owners:
                        info["owners"] = owners
                        self.locks[r] = info
                    else:
                        # no owners left; try promote waiters
                        q = self.waiting.get(r, [])
                        if q:
                            # if first waiter(s) are shared, promote all leading shared
                            promoted = []
                            first = q.pop(0)
                            if first.get("mode") == "shared":
                                promoted.append(first.get("node_id"))
                                # collect following shared waiters
                                while q and q[0].get("mode") == "shared":
                                    w = q.pop(0)
                                    promoted.append(w.get("node_id"))
                                self.locks[r] = {"mode": "shared", "owners": set(promoted)}
                            else:
                                # exclusive
                                self.locks[r] = {"mode": "exclusive", "owners": {first.get("node_id")}}
                            if q:
                                self.waiting[r] = q
                            else:
                                self.waiting.pop(r, None)
                        else:
                            self.locks.pop(r, None)
                    released.append(r)

            # remove victim from any waiting queues
            for r, q in list(self.waiting.items()):
                if victim in q:
                    q = [x for x in q if x != victim]
                    if q:
                        self.waiting[r] = q
                    else:
                        self.waiting.pop(r, None)

            victims.append((victim, released))

        return victims


class LockRoutesMixin:
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