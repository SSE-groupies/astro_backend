import asyncio
import time
import logging
from src.db.azure_tables import tables

logger = logging.getLogger(__name__)

async def delete_old_stars():
    """Periodically deletes stars older than 24 hours."""
    while True:
        try:
            current_time = time.time() - 1735689600  # Adjusted current time
            expiration_time = current_time - 86400  # 24 hours ago

            logger.info(f"Running garbage collection. Deleting stars before: {expiration_time}")

            all_stars = list(tables["Stars"].list_entities())

            for star in all_stars:
                last_like_time = star.get("LastLiked", 0)
                if last_like_time < expiration_time:
                    try:
                        tables["Stars"].delete_entity(star["PartitionKey"], star["RowKey"])
                        logger.info(f"Deleted expired star: {star['RowKey']}")
                    except Exception as e:
                        logger.warning(f"Failed to delete star {star['RowKey']}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in garbage collection: {str(e)}")

        await asyncio.sleep(1)  # Run every hour
