from taskiq_redis import ListQueueBroker
from config import settings

# Redis-backed broker using a simple list queue (LPUSH / BRPOP).
# One Redis connection is enough for development and moderate production load.
# Swap to RedisPipeline or add a result backend later if needed.
broker = ListQueueBroker(settings.redis_url)
