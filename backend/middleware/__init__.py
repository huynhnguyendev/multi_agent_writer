"""Export middleware setup functions."""

from backend.middleware.error_handler import register_error_handlers

__all__ = ["register_error_handlers"]