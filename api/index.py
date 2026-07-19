"""
Vercel API Route Entry Point
============================
Vercel automatically serves files in /api as serverless functions.
This file re-exports the FastAPI app for Vercel's Python runtime.
"""

from main import app