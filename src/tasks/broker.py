from utils.database.config import settings

# Use Redis-backed ListQueueBroker when Redis is configured (production/staging).
# Fall back to InMemoryBroker for local dev or CI where Redis is not available.
if settings.use_redis_broker:
    from taskiq_redis import ListQueueBroker
    broker = ListQueueBroker(settings.redis_url)
else:
    from taskiq import InMemoryBroker
    broker = InMemoryBroker()
