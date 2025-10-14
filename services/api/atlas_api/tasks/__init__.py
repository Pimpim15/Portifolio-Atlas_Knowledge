"""Tasks Celery."""

from .indexing import celery_app

__all__ = ["celery_app"]
