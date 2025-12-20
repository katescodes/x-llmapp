"""
Middleware to handle X-Force-Mode header for dev/testing
"""
import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cutover import set_forced_mode


class ForceModeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to read X-Force-Mode header and override cutover mode
    
    Only active when DEBUG=true (dev environment)
    """
    
    async def dispatch(self, request: Request, call_next):
        # Only in DEBUG mode
        debug_enabled = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        if debug_enabled:
            # Read X-Force-Mode header
            force_mode = request.headers.get("X-Force-Mode")
            
            if force_mode:
                # Valid modes: OLD, SHADOW, PREFER_NEW, NEW_ONLY
                valid_modes = {"OLD", "SHADOW", "PREFER_NEW", "NEW_ONLY"}
                if force_mode.upper() in valid_modes:
                    set_forced_mode(force_mode.upper())
                    # Add to response headers for debugging
                    response = await call_next(request)
                    response.headers["X-Actual-Mode"] = force_mode.upper()
                    return response
        
        # Normal processing
        set_forced_mode(None)
        response = await call_next(request)
        return response

