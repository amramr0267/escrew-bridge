import shutil
from typing import List

from fastapi import APIRouter, Depends, UploadFile
from fastapi.params import File, Path
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/me", response_model=schemas.UserResponse)
def get_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user




@router.get("/me/full-data", response_model=schemas.UserFullProfile)
async def get_user_full_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user_listings = db.query(models.Listing).filter(models.Listing.seller_id == current_user.id).all()
    
    history = db.query(models.Transaction).filter(
        (models.Transaction.buyer_id == current_user.id) | 
        (models.Transaction.seller_id == current_user.id)
    ).order_by(models.Transaction.created_at.desc()).all()
    
    # 🎯 THIS IS THE BRIDGE: Manually map the DB object to the Pydantic schema
    return {
        "user": schemas.UserRead.model_validate(current_user), 
        "listings": user_listings,
        "history": history
    }

@router.put("/update-phone")
async def update_phone_number(
    new_phone: str, # أو استخدم Schema
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.phone_number = new_phone
    db.commit()
    return {"message": "تم تحديث رقم الهاتف بنجاح."}

@router.get("/me/listings", response_model=List[schemas.ListingResponse])
async def get_my_listings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Fetch all listings where the seller_id matches the current_user's id
    listings = db.query(models.Listing).filter(
        models.Listing.seller_id == current_user.id
    ).order_by(models.Listing.id.desc()).all()
    
    return listings

# app/routers/users.py

@router.post("/verify-request")
async def request_verification(
    id_front: UploadFile = File(...),
    id_back: UploadFile = File(...),
    selfie_with_id: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Define where to save (ensure this folder exists on your server)
    UPLOAD_DIR = Path("app/uploads/verification")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def save_file(file: UploadFile) -> str:
        file_path = UPLOAD_DIR / f"{current_user.id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return str(file_path)

    # 2. Save the files and get their paths
    path_to_front = save_file(id_front)
    path_to_back = save_file(id_back)
    path_to_selfie = save_file(selfie_with_id)

    # 3. Now these variables are defined and ready for the database
    new_request = models.VerificationRequest(
        user_id=current_user.id,
        id_front_path=path_to_front,
        id_back_path=path_to_back,
        selfie_with_id_path=path_to_selfie
    )
    
    db.add(new_request)
    db.commit()
    return {"message": "تم إرسال طلب التوثيق بنجاح."}