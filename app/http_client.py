"""
Shared HTTP Client for all routers
"""
import httpx
import logging

logger = logging.getLogger(__name__)

# Global HTTP client instance (initialized in main.py)
http_client = None


def get_http_client():
    """Get the shared HTTP client instance"""
    return http_client


def set_http_client(client):
    """Set the shared HTTP client instance""
    global http_client
    http_client = client
