import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json
from typing import List, Dict

# Create separate routers for stars and users
router = APIRouter()
logger = logging.getLogger(__name__)

# Create event queues for SSE
connections: List[asyncio.Queue] = []  # one queue per SSE connection
# star_event_queue = asyncio.Queue()

@router.get("/stream")
async def stream_stars(request: Request):
    # 1) Create a new queue for this client
    queue = asyncio.Queue()
    # 2) Add it to the global list
    connections.append(queue)

    # 3) A generator that reads from *this* queue only
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {event}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            # 4) On disconnect, remove queue from global list
            connections.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
