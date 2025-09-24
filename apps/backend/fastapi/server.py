from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import os
import redis
import random
from celery import Celery
from utils import (
    generate_slug, store_context_metadata, get_context_metadata,
    get_all_contexts, update_context_stats, slug_exists
)

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

class ContextCreate(BaseModel):
    context: str
    description: Optional[str] = None
    generation_interval: int = 60

class ContextResponse(BaseModel):
    slug: str
    context: str
    url: str
    created_at: int
    active: bool

@app.get("/health")
async def health():
    try:
        # Test Redis connection
        r.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}

@app.get("/contexts/{slug}/next/{n}")
async def get_next_suggestions(
    slug: str = Path(..., description="Context slug"),
    n: int = Path(..., ge=1, le=100, description="Number of suggestions to retrieve")
):
    """Get next n suggestions from the FIFO queue for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        queue_key = f"suggestions:queue:{slug}"

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
            "context_id": slug,
            "context": context_metadata.get('context'),
            "remaining_in_queue": r.llen(queue_key)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving suggestions: {str(e)}")

# Legacy endpoint for backward compatibility
@app.get("/next/{n}")
async def get_next_suggestions_legacy(n: int = Path(..., ge=1, le=100, description="Number of suggestions to retrieve")):
    """Get next n suggestions from the FIFO queue (legacy endpoint)"""
    return await get_next_suggestions(CONTEXT_ID, n)

@app.get("/contexts/{slug}/random/{n}")
async def get_random_suggestions(
    slug: str = Path(..., description="Context slug"),
    n: int = Path(..., ge=1, le=100, description="Number of random suggestions to retrieve")
):
    """Get n random suggestions from the accumulated set for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        all_key = f"suggestions:all:{slug}"
        total_available = r.scard(all_key)

        if total_available == 0:
            return {
                "suggestions": [],
                "count": 0,
                "context_id": slug,
                "context": context_metadata.get('context'),
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
            "context_id": slug,
            "context": context_metadata.get('context'),
            "total_available": total_available,
            "sampled_with_replacement": n > actual_n
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving random suggestions: {str(e)}")

# Legacy endpoint for backward compatibility
@app.get("/random/{n}")
async def get_random_suggestions_legacy(n: int = Path(..., ge=1, le=100, description="Number of random suggestions to retrieve")):
    """Get n random suggestions from the accumulated set (legacy endpoint)"""
    return await get_random_suggestions(CONTEXT_ID, n)

@app.get("/contexts/{slug}/status")
async def get_status(slug: str = Path(..., description="Context slug")):
    """Get current queue and generation status for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        queue_key = f"suggestions:queue:{slug}"
        all_key = f"suggestions:all:{slug}"
        stats_key = f"stats:{slug}"

        queue_size = r.llen(queue_key)
        total_unique = r.scard(all_key)
        total_generated = int(r.hget(stats_key, "total_generated") or 0)
        last_generation = int(r.hget(stats_key, "last_generation") or 0)

        # Test Redis connection
        try:
            r.ping()
            redis_status = "connected"
        except Exception as redis_error:
            redis_status = f"disconnected: {str(redis_error)}"

        return {
            "context_id": slug,
            "context": context_metadata.get('context'),
            "description": context_metadata.get('description'),
            "created_at": context_metadata.get('created_at'),
            "active": context_metadata.get('active'),
            "queue_size": queue_size,
            "total_unique_suggestions": total_unique,
            "total_generated": total_generated,
            "last_generation_timestamp": last_generation,
            "redis_url": redis_url,
            "redis_status": redis_status,
            "healthy": redis_status == "connected"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {str(e)}")

# Legacy endpoint for backward compatibility
@app.get("/status")
async def get_status_legacy():
    """Get current queue and generation status (legacy endpoint)"""
    return await get_status(CONTEXT_ID)

@app.get("/contexts/{slug}/peek/{n}")
async def peek_next_suggestions(
    slug: str = Path(..., description="Context slug"),
    n: int = Path(..., ge=1, le=100, description="Number of suggestions to peek at")
):
    """Peek at next n suggestions without removing them from queue for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        queue_key = f"suggestions:queue:{slug}"

        # Get n items from the right side without removing them
        suggestions = r.lrange(queue_key, -n, -1)
        suggestions = [item.decode('utf-8') for item in reversed(suggestions)]

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "context_id": slug,
            "context": context_metadata.get('context'),
            "total_in_queue": r.llen(queue_key),
            "note": "These suggestions were not removed from the queue"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error peeking at suggestions: {str(e)}")

# Legacy endpoint for backward compatibility
@app.get("/peek/{n}")
async def peek_next_suggestions_legacy(n: int = Path(..., ge=1, le=100, description="Number of suggestions to peek at")):
    """Peek at next n suggestions without removing them from queue (legacy endpoint)"""
    return await peek_next_suggestions(CONTEXT_ID, n)

@app.post("/contexts", response_model=ContextResponse)
async def create_context(context_data: ContextCreate):
    """Create a new context with a unique slug"""
    try:
        # Generate unique slug
        slug = generate_slug(context_data.context)

        # Ensure uniqueness
        while slug_exists(r, slug):
            slug = generate_slug(context_data.context)

        # Store context metadata
        metadata = store_context_metadata(
            r,
            slug,
            context_data.context,
            {'description': context_data.description}
        )

        # Trigger initial generation for this context
        try:
            task = celery_app.send_task('worker.generate_suggestions_for_context', args=[slug, context_data.context])
        except Exception as e:
            print(f"Warning: Could not trigger initial generation: {e}")

        return ContextResponse(
            slug=slug,
            context=context_data.context,
            url=f"/contexts/{slug}",
            created_at=metadata['created_at'],
            active=metadata['active']
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating context: {str(e)}")

@app.get("/contexts")
async def list_contexts():
    """List all active contexts"""
    try:
        contexts = get_all_contexts(r)
        return {
            "contexts": contexts,
            "total": len(contexts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing contexts: {str(e)}")

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

@app.post("/contexts/{slug}/generate")
async def trigger_generation(slug: str = Path(..., description="Context slug")):
    """Manually trigger suggestion generation for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        # Trigger the generation task for this specific context
        task = celery_app.send_task('worker.generate_suggestions_for_context', args=[slug, context_metadata['context']])

        return {
            "message": "Generation task triggered",
            "task_id": task.id,
            "context_id": slug,
            "context": context_metadata.get('context'),
            "note": f"Check /contexts/{slug}/status endpoint for results"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering generation: {str(e)}")

# Legacy endpoint for backward compatibility
@app.post("/generate")
async def trigger_generation_legacy():
    """Manually trigger suggestion generation (legacy endpoint)"""
    return await trigger_generation(CONTEXT_ID)

@app.delete("/contexts/{slug}/clear")
async def clear_suggestions(slug: str = Path(..., description="Context slug")):
    """Clear all suggestions and start fresh for a specific context"""
    try:
        # Verify context exists
        context_metadata = get_context_metadata(r, slug)
        if not context_metadata:
            raise HTTPException(status_code=404, detail=f"Context '{slug}' not found")

        queue_key = f"suggestions:queue:{slug}"
        all_key = f"suggestions:all:{slug}"
        stats_key = f"stats:{slug}"

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
            "context_id": slug,
            "context": context_metadata.get('context')
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing suggestions: {str(e)}")

# Legacy endpoint for backward compatibility
@app.delete("/clear")
async def clear_suggestions_legacy():
    """Clear all suggestions and start fresh (legacy endpoint)"""
    return await clear_suggestions(CONTEXT_ID)

if __name__ == "__main__":
    PORT = int(os.getenv("BACKEND_PORT", 9812))
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
