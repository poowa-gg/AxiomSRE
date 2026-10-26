"""
AxiomSRE - Vercel Serverless Entry Point
Vercel's @vercel/python runtime looks for `app` in api/index.py
"""
from main import app  # noqa: F401 - re-export for Vercel
