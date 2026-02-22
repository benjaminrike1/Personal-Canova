from fastapi import APIRouter

router = APIRouter()


@router.get("/profile")
async def get_profile():
    """Get the athlete profile."""
    return None


@router.post("/profile")
async def create_profile():
    """Create athlete profile (onboarding)."""
    return {}


@router.put("/profile")
async def update_profile():
    """Update athlete profile."""
    return {}


@router.get("/onboarding-status")
async def onboarding_status():
    """Check if onboarding is complete."""
    return {"complete": False}
