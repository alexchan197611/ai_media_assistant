from fastapi import APIRouter
router = APIRouter(tags=["system"])
@router.get("/health")
def health(): return {"status": "ok"}

