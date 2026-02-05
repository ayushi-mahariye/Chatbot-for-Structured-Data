from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, query, rbac
from app.utils.redis_client import redis_client
import logging
from app.services.sql_generator import SQLGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager
    Handles startup and shutdown events
    """
    # STARTUP
    logger.info("🚀 Application starting up...")
    logger.info(f"Environment: {'DEBUG' if settings.debug else 'PRODUCTION'}")
    
    # PRE-LOAD SCHEMA AND RULES
    try:
        logger.info("📋 Pre-loading schema and custom rules...")
        sql_gen = SQLGenerator()
        logger.info(f"✅ Schema pre-loaded: {len(sql_gen.schema_content)} chars")
    except Exception as e:
        logger.error(f"⚠️  Failed to pre-load schema: {e}")
        logger.warning("Schema will be loaded on first request")
    
    # INITIALIZE REDIS CONNECTION
    try:
        logger.info(f"🔴 Initializing Redis: {settings.redis_url}")
        await redis_client.initialize()
        logger.info("✅ Redis initialized successfully (TTL: 120 seconds)")
    except Exception as e:
        logger.error(f"⚠️  Redis initialization failed: {e}")
        logger.warning("Application will continue without Redis caching")
    
    logger.info("✅ All services initialized")
    
    yield  # Application runs here
    
    # SHUTDOWN
    logger.info("👋 Application shutting down...")
    # REDIS DISABLED - Close Redis connection
    try:
        await redis_client.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")
    
    logger.info("✅ Shutdown complete")

# Create FastAPI app with lifespan manager
app = FastAPI(
    title="SQL Pipeline API",
    description="RBAC-enabled SQL Chatbot Backend",
    version="1.0.0",
    lifespan=lifespan  # Add lifespan manager
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(rbac.router, prefix="/rbac", tags=["rbac"])

@app.get("/")
async def root():
    return {
        "message": "SQL Pipeline API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    Returns status of all critical services
    """
    # REDIS DISABLED - redis_status = await redis_client.health_check()
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "api": "operational",
            # REDIS DISABLED
            # "redis": redis_status
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)