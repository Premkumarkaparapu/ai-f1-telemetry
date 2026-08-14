import time
from concurrent.futures import ThreadPoolExecutor
from backend.app.core.semaphore import ConcurrencySemaphore


def worker(sem, req_id, duration, results):
    acquired = sem.acquire_sync(req_id)
    if acquired:
        results.append(req_id)
        time.sleep(duration)
        sem.release_sync(req_id)


def test_semaphore_concurrency_limit():
    # Setup semaphore with limit of 3
    sem = ConcurrencySemaphore(limit=3, lease_ttl_seconds=5)

    # Clean up any residual keys in Redis first
    from backend.app.core.redis import get_redis_client
    redis_client = get_redis_client()
    if redis_client:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(redis_client.delete("gemini_semaphore"))
        finally:
            loop.close()

    results = []
    # Submit 10 concurrent requests to a thread pool
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(10):
            executor.submit(worker, sem, f"req-{i}", 0.2, results)

    # Since the limit is 3, only 3 requests should be able to acquire
    # the semaphore concurrently in the first batch. The remaining 7
    # should fail to acquire it because worker does not retry.
    assert len(results) <= 3
    assert len(results) > 0
