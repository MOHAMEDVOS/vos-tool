"""Shared SSE (Server-Sent Events) streaming helper.

Collapses the "background worker thread -> queue -> generator -> StreamingResponse"
scaffold that was independently reinvented across:
  * backend/api/readymode_users.py — 4 copies (create/delete/duplicates/inactive),
    synchronous blocking generator, no keep-alive or client-disconnect/cancellation
    handling.
  * backend/api/scoring.py — 2 copies (gather/audit), async generator with
    keep-alive pings and cancel_event-based cancellation. The most complete style.
  * backend/api/readymode.py — 1 copy (/stream), log lines sourced from a
    thread-local stdout proxy instead of an explicit log callback, cancelled via
    an _active_runs registry (that registry lives in readymode.py, not here —
    this helper only needs the one cancel_event a run wants set on disconnect).

Usage
-----
    def worker(emitter: SSEEmitter) -> None:
        try:
            ... do the real work, call emitter.send(event, data) for progress ...
            emitter.send("done", json.dumps(result))
        except Exception as e:
            emitter.send("error", str(e))

    return run_sse_stream(worker, start=("start", "Audit started"))

`worker` runs on a background daemon thread and is responsible for sending its
own terminal event ("done" / "error" / "cancelled" / whatever an endpoint
needs) as its last action — this helper does not interpret event names, so the
2-way / 3-way / 4-way outcome branching each endpoint already had stays exactly
where it was, just inlined instead of being reconstructed from a `result_box`
after the fact. The emitter's queue is closed automatically once `worker`
returns or raises, even if it forgot to send a terminal event, so the stream
can never hang open.

Cancellation and keep-alive pings are opt-in/out per call so this one helper
covers both the full-featured style (scoring.py) and the bare style
(readymode_users.py) without forcing one shape on the other.
"""

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Callable, Optional, Tuple

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

_SENTINEL = None  # queue item meaning "worker is done, no more events are coming"
_PING = ": ping\n\n"

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # disable nginx/Railway buffering of the stream
}


def format_sse(event: str, data: Any) -> str:
    """Format one SSE `data:` line — the exact shape every duplicated local
    `_sse()` used.

    `data` is embedded as-is, not re-stringified here. Existing call sites pass
    different shapes on purpose (a plain string, a pre-`json.dumps`'d string, or
    a raw dict/list) and the webapp's `readSSEStream` just forwards whatever
    `data` deserializes to — so keep passing whatever shape the pre-refactor
    `_sse(...)` call at that site used, or a client parsing a specific shape
    downstream will break.
    """
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


class SSEEmitter:
    """Queue-backed channel a background worker uses to push SSE events."""

    def __init__(self) -> None:
        self._q: "queue.Queue[Optional[Tuple[str, Any]]]" = queue.Queue()

    def send(self, event: str, data: Any) -> None:
        """Push one (event, data) pair; it's formatted lazily at yield-time."""
        self._q.put((event, data))

    def _close(self) -> None:
        self._q.put(_SENTINEL)

    def _get_nowait(self):
        return self._q.get_nowait()


def run_sse_stream(
    worker: Callable[[SSEEmitter], None],
    *,
    start: Optional[Tuple[str, Any]] = None,
    cancel_event: Optional[threading.Event] = None,
    keepalive: bool = True,
    poll_interval: float = 0.2,
    disconnect_log: Optional[Callable[[], None]] = None,
) -> StreamingResponse:
    """Run `worker` on a background thread and stream its events as SSE.

    worker(emitter)   -- runs in a daemon thread; call emitter.send(event, data)
                          for each progress/terminal message. Must send its own
                          terminal event before returning — this helper only
                          guarantees the stream closes, not what gets said.
    start             -- optional (event, data) yielded before anything else,
                          same as every existing endpoint's "start" line. Leave
                          unset for endpoints that never sent one.
    cancel_event      -- if given, .set() when the client disconnects, so a
                          worker that polls it can stop early. Leave unset for
                          endpoints with no cancellation support.
    keepalive         -- if True, yield ": ping\\n\\n" while waiting on an empty
                          queue so intermediary proxies don't time out the
                          connection. Endpoints that never sent pings keep
                          keepalive=False so nothing new appears on the wire.
    poll_interval     -- seconds between empty-queue polls (and, if keepalive,
                          between pings). 0.2s matches every existing copy.
    disconnect_log    -- optional zero-arg callback invoked once on disconnect
                          (CancelledError or GeneratorExit), before re-raising,
                          so each endpoint can keep its own log wording.
    """
    emitter = SSEEmitter()

    def _thread_target() -> None:
        try:
            worker(emitter)
        except Exception:
            # Safety net only: every current worker already catches its own
            # exceptions and reports them as an "error" event. This just
            # guarantees the sentinel still gets sent (so the generator below
            # can't hang forever) if a future worker ever forgets to.
            logger.exception("Unhandled exception in SSE worker thread")
        finally:
            emitter._close()

    threading.Thread(target=_thread_target, daemon=True).start()

    async def event_stream():
        try:
            if start is not None:
                yield format_sse(*start)
            while True:
                try:
                    item = emitter._get_nowait()
                except queue.Empty:
                    await asyncio.sleep(poll_interval)
                    if keepalive:
                        yield _PING
                    continue
                if item is _SENTINEL:
                    break
                event, data = item
                yield format_sse(event, data)
        except (asyncio.CancelledError, GeneratorExit):
            if cancel_event is not None:
                cancel_event.set()
            if disconnect_log is not None:
                disconnect_log()
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=dict(_SSE_HEADERS),
    )
