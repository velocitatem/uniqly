import os
import time
import json
import subprocess
import sys
from typing import List
from celery import Celery
import redis
from llms import generate_contextual_suggestions

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
app = Celery('worker', broker=redis_url, backend=redis_url)
r = redis.from_url(redis_url)

# Configuration
CONTEXT_X = os.getenv("CONTEXT_X", "creative writing prompts for sci-fi stories")
CONTEXT_ID = os.getenv("CONTEXT_ID", "default")
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "1000"))
GENERATION_INTERVAL = int(os.getenv("GENERATION_INTERVAL", "60"))
LLM_SCRIPT_PATH = os.getenv("LLM_SCRIPT_PATH", "/app/src/llm/main.py")

@app.task
def generate_suggestions():
    """Generate suggestions using local llms.py module and store in Redis"""
    try:
        # Generate suggestions directly using imported function
        suggestions = generate_contextual_suggestions(CONTEXT_X)

        if not suggestions:
            return {"message": "No suggestions generated"}

        # Store in Redis
        queue_key = f"suggestions:queue:{CONTEXT_ID}"
        all_key = f"suggestions:all:{CONTEXT_ID}"

        # Add to FIFO queue (with size limit)
        pipe = r.pipeline()
        for suggestion in suggestions:
            pipe.lpush(queue_key, suggestion)
            pipe.sadd(all_key, suggestion)

        # Trim queue to max size
        pipe.ltrim(queue_key, 0, MAX_QUEUE_SIZE - 1)
        pipe.execute()

        # Update generation stats
        stats_key = f"stats:{CONTEXT_ID}"
        r.hincrby(stats_key, "total_generated", len(suggestions))
        r.hset(stats_key, "last_generation", int(time.time()))

        print(f"Generated {len(suggestions)} suggestions for context '{CONTEXT_X}'")
        return {
            "generated": len(suggestions),
            "queue_size": r.llen(queue_key),
            "total_unique": r.scard(all_key)
        }

    except Exception as e:
        print(f"Error in generate_suggestions: {str(e)}")
        return {"error": str(e)}

@app.task
def get_queue_status():
    """Get current queue status"""
    queue_key = f"suggestions:queue:{CONTEXT_ID}"
    all_key = f"suggestions:all:{CONTEXT_ID}"
    stats_key = f"stats:{CONTEXT_ID}"

    return {
        "context": CONTEXT_X,
        "context_id": CONTEXT_ID,
        "queue_size": r.llen(queue_key),
        "total_unique": r.scard(all_key),
        "total_generated": int(r.hget(stats_key, "total_generated") or 0),
        "last_generation": int(r.hget(stats_key, "last_generation") or 0)
    }

@app.task
def cleanup_old_suggestions(max_age_days=7):
    """Cleanup old suggestions to prevent memory issues"""
    # This could be enhanced to track suggestion timestamps
    # For now, just ensure we don't exceed limits
    all_key = f"suggestions:all:{CONTEXT_ID}"
    total_count = r.scard(all_key)

    if total_count > MAX_QUEUE_SIZE * 2:
        # Remove random elements to get back to reasonable size
        excess = total_count - MAX_QUEUE_SIZE
        for _ in range(excess):
            r.spop(all_key)

        return {"cleaned": excess, "remaining": r.scard(all_key)}

    return {"cleaned": 0, "total": total_count}

# Schedule periodic generation
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Generate suggestions every GENERATION_INTERVAL seconds
    sender.add_periodic_task(
        GENERATION_INTERVAL,
        generate_suggestions.s(),
        name=f'generate-suggestions-{CONTEXT_ID}'
    )

    # Cleanup every hour
    sender.add_periodic_task(
        3600.0,
        cleanup_old_suggestions.s(),
        name=f'cleanup-{CONTEXT_ID}'
    )

# Legacy tasks for compatibility
@app.task
def simple_task(message):
    """A simple task that processes a message and returns a result"""
    time.sleep(2)  # Simulate some work
    return f"Processed: {message}"

@app.task
def add_numbers(x, y):
    """Simple math task"""
    return x + y

if __name__ == '__main__':
    app.start()