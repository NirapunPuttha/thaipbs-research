from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def user_status():
    return {"message": "Users endpoints - Coming soon"}