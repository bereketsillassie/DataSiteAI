"""
app/api/v1/router.py
─────────────────────
Mounts all v1 sub-routers under /api/v1.
Each endpoint group has its own file and router instance.
"""

from fastapi import APIRouter

from app.api.v1 import health, analyze, layers, scores, listings, scoring_schema

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(analyze.router, tags=["analysis"])
router.include_router(layers.router, tags=["layers"])
router.include_router(scores.router, tags=["scores"])
router.include_router(listings.router, tags=["listings"])
router.include_router(scoring_schema.router, tags=["scoring"])
