"""
CI/CD Test Endpoint
GET /test/cicd - Returns deployment info
"""

from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

@router.get("/test/cicd")
async def test_cicd():
    """Test endpoint to verify CI/CD deployment"""
    return {
        "status": "success",
        "service": "Goalixa BFF",
        "message": "CI/CD pipeline is working! 🚀",
        "deployed_at": datetime.utcnow().isoformat(),
        "version": "test-cicd"
    }
