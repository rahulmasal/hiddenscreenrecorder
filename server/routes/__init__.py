"""
Routes package for Screen Recorder Server
"""

from .api import api_bp, legacy_bp

__all__ = ["api_bp", "legacy_bp"]
