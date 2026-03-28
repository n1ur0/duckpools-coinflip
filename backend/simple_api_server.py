"""
Simplified API Server for Security Header Testing

This is a minimal FastAPI server with security headers middleware.
Used only for testing the implementation of security headers.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard security headers on all responses.
    
    MAT-218: Fixed security headers implementation to include:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restrictive settings
    - Content-Security-Policy: default restrictive policy
    - Strict-Transport-Security: HSTS (production only)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Apply security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        
        # Content Security Policy - prevent XSS and data injection
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )
        
        # Strict Transport Security - only in production with HTTPS
        # For development, we'll add it but with max-age=0 to disable
        response.headers["Strict-Transport-Security"] = "max-age=0; includeSubDomains"
        
        # Debug header to verify middleware is running
        response.headers["X-Security-Middleware"] = "active"
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    yield
    # Cleanup on shutdown


# ─── App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="DuckPools Security Test API",
    description="Minimal API for testing security headers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS_STR", "http://localhost:3000")
cors_origins = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Reduced CSRF risk
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Key", "Accept", "Origin"],
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)


# ─── Root Endpoints ─────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "DuckPools Security Test API",
        "version": "1.0.0",
        "purpose": "Security header testing"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/pool/state")
async def pool_state():
    """Mock pool state endpoint."""
    return {
        "bankroll": "1000000000000",
        "total_supply": "500000000000",
        "apy": "5.2"
    }


@app.get("/scripts")
async def scripts():
    """Mock scripts endpoint."""
    return {"scripts": []}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)