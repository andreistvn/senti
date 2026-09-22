"""
MultiChain JSON-RPC client for the SentiNet 'Bayanihan' (Tier 3) collaborative ledger.

This module owns every conversation with the MultiChain node:

  * MultiChainClient  — a thin, connection-pooling JSON-RPC wrapper that speaks
    the handful of MultiChain commands we need (getinfo, liststreams, create,
    subscribe, publish, liststreamitems).
  * LedgerWorker      — a background thread that owns all blocking RPC I/O so the
    FastAPI/Socket.io event loop never stalls waiting on the chain. It publishes
    queued threat reports, retries them when the node is down, keeps a cached
    health snapshot for /telemetry/summary, and periodically reconciles the local
    ledger mirror with what is actually on-chain (including items published by
    *other* relay nodes).

state.py wires the worker to SQLite through callbacks so this module stays free of
any database dependency.
"""

import queue
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter

from config import (
    MULTICHAIN_RPC_URL,
    MULTICHAIN_RPC_USER,
    MULTICHAIN_RPC_PASSWORD,
    MULTICHAIN_STREAM_NAME,
    MULTICHAIN_RPC_TIMEOUT,
    MULTICHAIN_AUTO_CREATE_STREAM,
    MULTICHAIN_SYNC_INTERVAL,
    MULTICHAIN_QUEUE_SIZE,
    MULTICHAIN_MAX_PUBLISH_ATTEMPTS,
    MULTICHAIN_LEDGER_FETCH_COUNT,
)

# MultiChain error codes we treat as "the stream simply isn't there yet".
_ERR_NOT_FOUND = (-708, -705, -100)


class MultiChainError(RuntimeError):
    """A JSON-RPC level error returned by the MultiChain node."""

    def __init__(self, code: Optional[int], message: str):
        super().__init__(f"[{code}] {message}" if code is not None else message)
        self.code = code
        self.message = message


class MultiChainClient:
    """Synchronous JSON-RPC client. All calls block; only the worker thread uses it."""

    def __init__(
        self,
        url: str = MULTICHAIN_RPC_URL,
        user: str = MULTICHAIN_RPC_USER,
        password: str = MULTICHAIN_RPC_PASSWORD,
        stream: str = MULTICHAIN_STREAM_NAME,
        timeout: float = MULTICHAIN_RPC_TIMEOUT,
    ):
        self.url = url
        self.stream = stream
        self.timeout = timeout

        # A pooled session keeps the TCP connection warm between publishes, which
        # matters when Tier 2 fires several reports a second during a flood.
        self._http = requests.Session()
        self._http.auth = (user, password)
        adapter = HTTPAdapter(pool_connections=2, pool_maxsize=4)
        self._http.mount('http://', adapter)
        self._http.mount('https://', adapter)

        self.last_latency_ms: int = 0

    def call(self, method: str, *params: Any) -> Any:
        """
        Execute a single JSON-RPC command.

        Raises MultiChainError for node-level errors (bad params, missing stream,
        bad credentials) and requests.RequestException when the node is unreachable.
        """
        payload = {
            'method': method,
            'params': list(params),
            'id': str(uuid.uuid4()),
        }

        started = time.perf_counter()
        response = self._http.post(self.url, json=payload, timeout=self.timeout)
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)

        # MultiChain answers RPC-level failures with a non-200 status *and* a JSON
        # body carrying the real error, so parse the body before trusting the code.
        try:
            body = response.json()
        except ValueError:
            raise MultiChainError(response.status_code, response.text.strip() or 'non-JSON RPC response')

        error = body.get('error')
        if error:
            if isinstance(error, dict):
                raise MultiChainError(error.get('code'), error.get('message', 'unknown RPC error'))
            raise MultiChainError(None, str(error))

        if response.status_code != 200:
            raise MultiChainError(response.status_code, response.text.strip())

        return body.get('result')

    # ─── Commands ───────────────────────────────────────────────────────────

    def get_info(self) -> Dict[str, Any]:
        """`getinfo` — node version, chain name and current block height."""
        return self.call('getinfo') or {}

    def stream_info(self) -> Optional[Dict[str, Any]]:
        """`liststreams` for our stream, or None if the node doesn't know it."""
        try:
            result = self.call('liststreams', self.stream, True)
        except MultiChainError as exc:
            if exc.code in _ERR_NOT_FOUND:
                return None
            raise
        return result[0] if result else None

    def ensure_stream(self) -> Dict[str, Any]:
        """
        Idempotently guarantee the threat stream exists and this node is subscribed.

        Creating the stream requires the node's wallet address to hold the `create`
        permission; on a single-node testbed the genesis address has it by default.
        """
        info = self.stream_info()

        if info is None:
            if not MULTICHAIN_AUTO_CREATE_STREAM:
                raise MultiChainError(None, f"stream '{self.stream}' does not exist and auto-create is disabled")
            print(f"[MultiChain] Stream '{self.stream}' not found — creating it (open stream).")
            self.call('create', 'stream', self.stream, True)
            info = self.stream_info() or {}

        if not info.get('subscribed', False):
            print(f"[MultiChain] Subscribing to stream '{self.stream}'.")
            self.call('subscribe', self.stream)
            info = self.stream_info() or info

        return info

    def publish_threat(self, key: str, data: Dict[str, Any]) -> str:
        """`publish` one threat record. Returns the transaction id."""
        txid = self.call('publish', self.stream, key, {'json': data})
        if not isinstance(txid, str) or not txid:
            raise MultiChainError(None, f'publish returned an unexpected result: {txid!r}')
        return txid

    def list_stream_items(self, count: int = MULTICHAIN_LEDGER_FETCH_COUNT) -> List[Dict[str, Any]]:
        """`liststreamitems` — the most recent `count` items on the threat stream."""
        result = self.call('liststreamitems', self.stream, False, count)
        return result if isinstance(result, list) else []

    def close(self) -> None:
        self._http.close()


# ─── Stream item decoding ───────────────────────────────────────────────────

def decode_stream_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Flatten a raw `liststreamitems` entry into the shape the dashboard ledger uses.

    Returns None for items we can't interpret (binary payloads, off-chain items
    whose data this node hasn't retrieved, or records written by another tool).
    """
    data = item.get('data')
    if not isinstance(data, dict) or 'json' not in data:
        # Hex/text payloads, or `{"size":..,"txid":..}` stubs for unavailable
        # off-chain data — nothing useful to show.
        return None

    fields = data['json']
    if not isinstance(fields, dict):
        return None

    txid = item.get('txid', '')

    # `keys` is the modern field; older MultiChain builds emit a singular `key`.
    keys = item.get('keys') or ([item['key']] if item.get('key') else [])
    mac = keys[0] if keys else fields.get('sourceMac', 'UNKNOWN')

    timestamp = fields.get('timestamp')
    if not timestamp:
        blocktime = item.get('blocktime')
        timestamp = time.strftime('%H:%M:%S', time.localtime(blocktime)) if blocktime else '--:--:--'

    return {
        'txid': txid,
        'blockId': txid[:8] if txid else '0xUNKNOWN',
        'timestamp': timestamp,
        'macHash': mac,
        'score': str(fields.get('score', 'N/A')),
        'confirmations': item.get('confirmations', 0),
    }


# ─── Background worker ──────────────────────────────────────────────────────

class LedgerWorker:
    """
    Owns the client and runs every blocking RPC on its own thread.

    Callers (the Socket.io handlers) only ever touch `submit()` and `snapshot()`,
    both of which are non-blocking.
    """

    def __init__(
        self,
        client: MultiChainClient,
        on_published: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_reconciled: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        sync_interval: float = MULTICHAIN_SYNC_INTERVAL,
    ):
        self._client = client
        self._on_published = on_published
        self._on_reconciled = on_reconciled
        self._sync_interval = sync_interval

        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=MULTICHAIN_QUEUE_SIZE)
        self._retry: List[Dict[str, Any]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            'online': False,
            'streamReady': False,
            'blockHeight': 0,
            'latencyMs': 0,
            'chainName': None,
            'lastError': None,
            'lastSyncAt': None,
            'published': 0,
            'dropped': 0,
            'pending': 0,
        }

    # ── Public, non-blocking API ────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='multichain-ledger', daemon=True)
        self._thread.start()
        print(f"[MultiChain] Ledger worker started (node={self._client.url}, stream={self._client.stream}).")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._client.close()

    def submit(self, record: Dict[str, Any]) -> bool:
        """
        Queue a threat record for publication. Returns False if the queue is full.

        Never blocks: during a 1,000 PPS flood the event loop must keep servicing
        blacklist broadcasts even if the chain is slow or down.
        """
        try:
            self._queue.put_nowait({'record': record, 'attempts': 0})
        except queue.Full:
            with self._lock:
                self._state['dropped'] += 1
            print('[MultiChain] Publish queue is full — dropping threat record.')
            return False
        return True

    def snapshot(self) -> Dict[str, Any]:
        """The most recent cached chain health. Safe to call from async handlers."""
        with self._lock:
            snap = dict(self._state)
        snap['pending'] = self._queue.qsize() + len(self._retry)
        return snap

    # ── Worker internals ────────────────────────────────────────────────────

    def _set(self, **fields: Any) -> None:
        with self._lock:
            self._state.update(fields)

    def _run(self) -> None:
        last_sync = 0.0

        while not self._stop.is_set():
            # Wait for work, but wake up often enough to run the heartbeat.
            timeout = max(0.5, min(self._sync_interval, 2.0))
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                item = None

            if item is not None:
                self._publish(item)

            now = time.monotonic()
            if now - last_sync >= self._sync_interval:
                last_sync = now
                self._heartbeat()

        print('[MultiChain] Ledger worker stopped.')

    def _publish(self, item: Dict[str, Any]) -> None:
        """Publish one queued record; park it for retry if the node isn't cooperating."""
        record = item['record']
        item['attempts'] += 1

        try:
            if not self._state['streamReady']:
                self._bootstrap()

            txid = self._client.publish_threat(record['sourceMac'], {
                'timestamp': record['timestamp'],
                'attackType': record.get('attackType', 'Unknown'),
                'score': record.get('confidence', 'N/A'),
                'tier': record.get('tier', 'Tier 3'),
                'action': record.get('action', 'Blocked'),
            })
        except (MultiChainError, requests.exceptions.RequestException) as exc:
            self._note_failure(exc)
            if item['attempts'] >= MULTICHAIN_MAX_PUBLISH_ATTEMPTS:
                with self._lock:
                    self._state['dropped'] += 1
                print(
                    f"[MultiChain] Giving up on {record.get('sourceMac')} after "
                    f"{item['attempts']} attempts: {exc}"
                )
            else:
                self._retry.append(item)
            return

        self._set(online=True, lastError=None, latencyMs=self._client.last_latency_ms)
        with self._lock:
            self._state['published'] += 1

        print(f"[MultiChain] Published {record.get('sourceMac')} to '{self._client.stream}' (txid {txid[:12]}…).")

        if self._on_published:
            entry = {
                'txid': txid,
                'blockId': txid[:8],
                'timestamp': record['timestamp'],
                'macHash': record['sourceMac'],
                'score': record.get('confidence', 'N/A'),
            }
            try:
                self._on_published(entry)
            except Exception as exc:  # a mirror failure must not kill the worker
                print(f'[MultiChain] Failed to mirror ledger entry locally: {exc}')

    def _bootstrap(self) -> None:
        """Verify the node is up and the threat stream is usable."""
        info = self._client.get_info()
        stream = self._client.ensure_stream()
        self._set(
            online=True,
            streamReady=True,
            blockHeight=int(info.get('blocks', 0) or 0),
            chainName=info.get('chainname'),
            latencyMs=self._client.last_latency_ms,
            lastError=None,
        )
        print(
            f"[MultiChain] Connected to '{info.get('chainname', 'chain')}' "
            f"v{info.get('version', '?')} at height {info.get('blocks', 0)}; "
            f"stream '{self._client.stream}' has {stream.get('items', 0)} items."
        )

    def _heartbeat(self) -> None:
        """Refresh the cached health snapshot, retry parked publishes, resync the mirror."""
        try:
            if not self._state['streamReady']:
                self._bootstrap()
            else:
                info = self._client.get_info()
                self._set(
                    online=True,
                    blockHeight=int(info.get('blocks', 0) or 0),
                    chainName=info.get('chainname'),
                    latencyMs=self._client.last_latency_ms,
                    lastError=None,
                )
        except (MultiChainError, requests.exceptions.RequestException) as exc:
            self._note_failure(exc)
            return

        self._set(lastSyncAt=time.time())

        # Re-drive anything that failed while the node was unreachable.
        parked, self._retry = self._retry, []
        for item in parked:
            if self._stop.is_set():
                self._retry.append(item)
                break
            self._publish(item)

        self._reconcile()

    def _reconcile(self) -> None:
        """
        Pull recent on-chain items into the local mirror.

        This is what makes the dashboard genuinely decentralized: threats published
        by peer relay nodes land here too, not just the ones this node wrote.
        """
        if not self._on_reconciled:
            return

        try:
            items = self._client.list_stream_items()
        except (MultiChainError, requests.exceptions.RequestException) as exc:
            self._note_failure(exc)
            return

        entries = [decoded for decoded in (decode_stream_item(i) for i in items) if decoded]
        if not entries:
            return

        try:
            self._on_reconciled(entries)
        except Exception as exc:
            print(f'[MultiChain] Ledger reconciliation failed: {exc}')

    def _note_failure(self, exc: Exception) -> None:
        """Record a failure once, without spamming the console on every retry."""
        message = str(exc)
        with self._lock:
            was_online = self._state['online']
            previous_error = self._state['lastError']

        if isinstance(exc, MultiChainError):
            # The node answered — it's reachable, just unhappy with the request.
            self._set(online=True, streamReady=False, lastError=message)
            print(f'[MultiChain] RPC error: {message}')
        else:
            self._set(online=False, streamReady=False, lastError=message)
            if was_online or previous_error != message:
                print(f'[MultiChain] Node unreachable at {self._client.url}: {message}')
                print('[MultiChain] Threat records will be queued and republished once it returns.')
