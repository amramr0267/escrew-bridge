from http.client import HTTPException
import shutil
from typing import List
from pathlib import Path  # Keep this one
from app.routers.notifications import send_notification
from fastapi import APIRouter, Depends, UploadFile, File # Import File here
from sqlalchemy.orm import Session
# REMOVE 'Path' from the fastapi.params import line above if it exists
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.security import get_current_user
from supabase import create_client
router = APIRouter(prefix="/api/users", tags=["Users"])
import os


supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])



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
    # دالة مساعدة لرفع الملف إلى Supabase
    def upload_to_supabase(file: UploadFile, folder: str) -> str:
        file_path = f"verifications/{current_user.id}/{folder}_{file.filename}"
        # رفع الملف مباشرة دون حفظه في /tmp
        supabase.storage.from_("identity-verifications").upload(
            path=file_path,
            file=file.file.read(),
            file_options={"content-type": file.content_type}
        )
        return file_path

    # رفع الملفات الثلاثة
    try:
        path_front = upload_to_supabase(id_front, "front")
        path_back = upload_to_supabase(id_back, "back")
        path_selfie = upload_to_supabase(selfie_with_id, "selfie")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل رفع الملفات: {str(e)}")

    # حفظ المسارات في قاعدة البيانات (Neon)
    new_request = models.VerificationRequest(
        user_id=current_user.id,
        id_front_path=path_front,
        id_back_path=path_back,
        selfie_with_id_path=path_selfie
    )
    
    # بقية منطق الإخطار وتحديث الحالة
    admin_user = db.query(models.User).filter(models.User.role == 'admin').first()
    if admin_user:
        send_notification(db=db, user_id=admin_user.id, message=f"المستخدم {current_user.username} قام برفع وثائق للتوثيق.")
    
    db.add(new_request)
    current_user.verification_status = "pending"
    db.commit()
    
    return {"message": "تم إرسال طلب التوثيق بنجاح."}