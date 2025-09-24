from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn
import os
import redis
import random
from celery import Celery

app = FastAPI(title="Infinite Suggestion Generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(redis_url)

# Celery connection for triggering tasks
celery_app = Celery('worker', broker=redis_url, backend=redis_url)

# Configuration
CONTEXT_ID = os.getenv("CONTEXT_ID", "default")

class ConfigUpdate(BaseModel):
    context: str
    generation_interval: int = 60

@app.get("/health")
async def health():
    try:
        # Test Redis connection
        r.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}

@app.get("/next/{n}")
async def get_next_suggestions(n: int = Path(..., ge=1, le=100, description="Number of suggestions to retrieve")):
    """Get next n suggestions from the FIFO queue"""
    try:
        queue_key = f"suggestions:queue:{CONTEXT_ID}"

        # Get n items from the right side of the list (FIFO)
        suggestions = []
        with r.pipeline() as pipe:
            for _ in range(n):
                pipe.rpop(queue_key)
            results = pipe.execute()

        suggestions = [item.decode('utf-8') for item in results if item is not None]

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "context_id": CONTEXT_ID,
            "remaining_in_queue": r.llen(queue_key)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving suggestions: {str(e)}")

@app.get("/random/{n}")
async def get_random_suggestions(n: int = Path(..., ge=1, le=100, description="Number of random suggestions to retrieve")):
    """Get n random suggestions from the accumulated set"""
    try:
        all_key = f"suggestions:all:{CONTEXT_ID}"
        total_available = r.scard(all_key)

        if total_available == 0:
            return {
                "suggestions": [],
                "count": 0,
                "context_id": CONTEXT_ID,
                "total_available": 0,
                "message": "No suggestions available yet. Worker may still be generating."
            }

        # Get random samples (with replacement if n > available)
        actual_n = min(n, total_available)
        suggestions = []

        if actual_n == total_available:
            # Get all suggestions if requested amount equals available
            suggestions = [item.decode('utf-8') for item in r.smembers(all_key)]
        else:
            # Get random samples
            suggestions = [item.decode('utf-8') for item in r.srandmember(all_key, actual_n)]

        # If we need more than available, sample with replacement
        if n > actual_n:
            additional_needed = n - actual_n
            additional = random.choices(suggestions, k=additional_needed)
            suggestions.extend(additional)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "context_id": CONTEXT_ID,
            "total_available": total_available,
            "sampled_with_replacement": n > actual_n
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving random suggestions: {str(e)}")

@app.get("/status")
async def get_status():
    """Get current queue and generation status"""
    try:
        queue_key = f"suggestions:queue:{CONTEXT_ID}"
        all_key = f"suggestions:all:{CONTEXT_ID}"
        stats_key = f"stats:{CONTEXT_ID}"

        queue_size = r.llen(queue_key)
        total_unique = r.scard(all_key)
        total_generated = int(r.hget(stats_key, "total_generated") or 0)
        last_generation = int(r.hget(stats_key, "last_generation") or 0)

        # Get context info
        context_x = os.getenv("CONTEXT_X", "Not configured")

        # Test Redis connection
        try:
            r.ping()
            redis_status = "connected"
        except Exception as redis_error:
            redis_status = f"disconnected: {str(redis_error)}"

        return {
            "context_id": CONTEXT_ID,
            "context": context_x,
            "queue_size": queue_size,
            "total_unique_suggestions": total_unique,
            "total_generated": total_generated,
            "last_generation_timestamp": last_generation,
            "redis_url": redis_url,
            "redis_status": redis_status,
            "healthy": redis_status == "connected"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {str(e)}")

@app.get("/peek/{n}")
async def peek_next_suggestions(n: int = Path(..., ge=1, le=100, description="Number of suggestions to peek at")):
    """Peek at next n suggestions without removing them from queue"""
    try:
        queue_key = f"suggestions:queue:{CONTEXT_ID}"

        # Get n items from the right side without removing them
        suggestions = r.lrange(queue_key, -n, -1)
        suggestions = [item.decode('utf-8') for item in reversed(suggestions)]

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "context_id": CONTEXT_ID,
            "total_in_queue": r.llen(queue_key),
            "note": "These suggestions were not removed from the queue"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error peeking at suggestions: {str(e)}")

@app.post("/configure")
async def update_configuration(config: ConfigUpdate):
    """Update the context configuration (requires worker restart to take effect)"""
    try:
        # This would typically update environment variables or config files
        # For now, just return what would need to be set
        return {
            "message": "Configuration update received",
            "new_context": config.context,
            "new_interval": config.generation_interval,
            "note": "Worker needs to be restarted with new CONTEXT_X environment variable",
            "recommended_env": {
                "CONTEXT_X": config.context,
                "GENERATION_INTERVAL": config.generation_interval
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")

@app.post("/generate")
async def trigger_generation():
    """Manually trigger suggestion generation (useful for testing)"""
    try:
        # Trigger the generation task
        task = celery_app.send_task('worker.generate_suggestions')

        return {
            "message": "Generation task triggered",
            "task_id": task.id,
            "context_id": CONTEXT_ID,
            "note": "Check /status endpoint for results"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering generation: {str(e)}")

@app.delete("/clear")
async def clear_suggestions():
    """Clear all suggestions and start fresh (useful for testing or context changes)"""
    try:
        queue_key = f"suggestions:queue:{CONTEXT_ID}"
        all_key = f"suggestions:all:{CONTEXT_ID}"
        stats_key = f"stats:{CONTEXT_ID}"

        deleted_queue = r.delete(queue_key)
        deleted_all = r.delete(all_key)
        deleted_stats = r.delete(stats_key)

        return {
            "message": "All suggestions cleared",
            "cleared_keys": {
                "queue": deleted_queue,
                "all_suggestions": deleted_all,
                "stats": deleted_stats
            },
            "context_id": CONTEXT_ID
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing suggestions: {str(e)}")

if __name__ == "__main__":
    PORT = int(os.getenv("BACKEND_PORT", 9812))
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
