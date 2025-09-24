import hashlib
import random
import string
import time
from typing import Dict, Any, Optional
import redis
import json

def generate_slug(context: str) -> str:
    """Generate a unique slug from context description"""
    # Create base slug from context (first few words, cleaned)
    base_words = context.lower().split()[:3]
    base = '-'.join(''.join(c for c in word if c.isalnum()) for word in base_words)

    # Add random suffix for uniqueness
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    return f"{base}-{suffix}"

def store_context_metadata(r: redis.Redis, slug: str, context: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Store context metadata in Redis"""
    context_data = {
        'slug': slug,
        'context': context,
        'created_at': int(time.time()),
        'active': True,
        'total_generated': 0,
        'last_generation': 0,
        'subscribers': 0
    }

    if metadata:
        context_data.update(metadata)

    # Store in Redis hash
    context_key = f"contexts:{slug}"
    r.hset(context_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in context_data.items()})

    # Add to contexts list
    r.sadd("contexts:all", slug)

    return context_data

def get_context_metadata(r: redis.Redis, slug: str) -> Optional[Dict[str, Any]]:
    """Retrieve context metadata from Redis"""
    context_key = f"contexts:{slug}"
    data = r.hgetall(context_key)

    if not data:
        return None

    # Convert back to proper types
    result = {}
    for k, v in data.items():
        key = k.decode() if isinstance(k, bytes) else k
        value = v.decode() if isinstance(v, bytes) else v

        # Try to parse JSON for complex types
        try:
            if value.startswith(('{', '[')):
                result[key] = json.loads(value)
            elif value.isdigit():
                result[key] = int(value)
            elif value.lower() in ('true', 'false'):
                result[key] = value.lower() == 'true'
            else:
                result[key] = value
        except (json.JSONDecodeError, ValueError):
            result[key] = value

    return result

def get_all_contexts(r: redis.Redis) -> Dict[str, Dict[str, Any]]:
    """Get all active contexts with their metadata"""
    slugs = r.smembers("contexts:all")
    contexts = {}

    for slug_bytes in slugs:
        slug = slug_bytes.decode() if isinstance(slug_bytes, bytes) else slug_bytes
        context_data = get_context_metadata(r, slug)
        if context_data and context_data.get('active'):
            contexts[slug] = context_data

    return contexts

def update_context_stats(r: redis.Redis, slug: str, generated_count: int = 0, last_generation: Optional[int] = None):
    """Update context generation statistics"""
    context_key = f"contexts:{slug}"

    if generated_count > 0:
        r.hincrby(context_key, "total_generated", generated_count)

    if last_generation:
        r.hset(context_key, "last_generation", str(last_generation))

def slug_exists(r: redis.Redis, slug: str) -> bool:
    """Check if a slug already exists"""
    return r.sismember("contexts:all", slug)