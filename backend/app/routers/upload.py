from fastapi import APIRouter, UploadFile, File, HTTPException
router = APIRouter()

@router.post("")
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Only CSV/JSON allowed")
    return {"filename": file.filename, "content_type": file.content_type}
