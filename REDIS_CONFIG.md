# Redis Configuration

## Problem Addressed
The original issue was that the `/next/{n}` endpoint was failing with:
```
Error retrieving suggestions: Command # 1 (RPOP suggestions:queue:ai-startup-2026) of pipeline caused error: You can't write against a read only replica.
```

## Root Cause
The Redis instance was being configured as a read-only replica instead of a writable master instance.

## Solution
### 1. Redis Configuration File (`docker/redis.conf`)
- **Explicit Master Configuration**: Set `replica-read-only no` to ensure write operations
- **Proper Persistence**: AOF and RDB enabled for data durability
- **Network Configuration**: Bind to all interfaces within container
- **Memory Management**: LRU eviction policy for optimal performance

### 2. Docker Compose Updates
- **Health Checks**: Added Redis health checks to ensure service is ready
- **Proper Dependencies**: API and worker wait for Redis to be healthy
- **Explicit Database Selection**: Use `/0` database consistently
- **Configuration Mount**: Mount custom Redis config file

### 3. Environment Configuration
- **Consistent URLs**: Use same Redis URL format across all services
- **Database Specification**: Explicitly specify database 0 (`/0`)

## Configuration Details

### Redis Service Features
- **Writable Master**: Guaranteed write operations
- **Data Persistence**: Both AOF and RDB for reliability  
- **Health Monitoring**: Built-in health checks
- **Memory Optimization**: LRU eviction policy
- **Logging**: Proper log levels for debugging

### Connection Configuration
- **Internal Services**: `redis://redis:6379/0` (within Docker network)
- **External Access**: `redis://localhost:${REDIS_PORT}/0` (from host)
- **Database**: Always use database 0 for consistency

## Deployment
1. Redis starts with custom configuration ensuring writable mode
2. Health check confirms Redis is operational
3. Worker starts after Redis is healthy
4. API starts after both Redis and worker are ready

This eliminates the read-only replica issue by ensuring Redis is always configured as a writable master instance.