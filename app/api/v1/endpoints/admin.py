from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def admin_status():
    return {"message": "Admin endpoints - Coming soon"}