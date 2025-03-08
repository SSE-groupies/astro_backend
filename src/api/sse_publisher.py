"""
Publisher for Server-Sent Events.
This module provides functions to publish events to the SSE queues.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Union

# Import the event queues from the SSE module
from src.api.sse import connections

logger = logging.getLogger(__name__)

async def publish_star_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Publish an event to the star event queue.
    
    Args:
        event_type: Type of event (e.g., 'create', 'update', 'delete')
        data: Event data containing star information
    """
    event = {
        "type": event_type,
        "data": data
    }
    
    try:
        for queue in connections:
            queue.put_nowait(event)
        logger.debug(f"Published star event: {event_type}")
    except Exception as e:
        logger.error(f"Failed to publish star event: {str(e)}")


