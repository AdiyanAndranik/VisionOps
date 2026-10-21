from __future__ import annotations

import asyncio
import json

import asyncpg

CHANNEL = "visionops_events"


class Hub:
    """Fans messages from Postgres NOTIFY out to the sockets watching each run."""

    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = {}

    def subscribe(self, run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(run_id)
        if subs:
            subs.discard(q)
            if not subs:
                del self._subs[run_id]

    def publish(self, payload: str) -> None:
        try:
            msg = json.loads(payload)
            run_id = msg.pop("run_id")
        except (ValueError, KeyError, AttributeError):
            return
        for q in list(self._subs.get(run_id, ())):
            q.put_nowait(msg)


async def listen_forever(hub: Hub, dsn: str, ready: asyncio.Event) -> None:
    """One dedicated connection LISTENing on CHANNEL. Reconnects if it drops.
    Events that happen while it is down are not pushed, clients refetch over REST."""
    while True:
        conn = None
        try:
            conn = await asyncpg.connect(dsn)
            lost = asyncio.Event()
            conn.add_termination_listener(lambda _c: lost.set())
            await conn.add_listener(CHANNEL, lambda _c, _pid, _ch, payload: hub.publish(payload))
            ready.set()
            await lost.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            if conn is not None and not conn.is_closed():
                try:
                    await conn.close()
                except Exception:
                    pass
        await asyncio.sleep(2)