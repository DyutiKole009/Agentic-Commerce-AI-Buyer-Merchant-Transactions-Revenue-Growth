import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any
import json

class EventBus:
    def __init__(self):
        # session_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []
        self._subscribers[session_id].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        if session_id in self._subscribers:
            if queue in self._subscribers[session_id]:
                self._subscribers[session_id].remove(queue)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def emit(self, session_id: str, event_type: str, data: Dict[str, Any]):
        event_payload = {
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if session_id in self._subscribers:
            for queue in self._subscribers[session_id]:
                await queue.put(event_payload)

event_bus = EventBus()
