from http.client import HTTPException
import shutil
from typing import List
from pathlib import Path  # Keep this one
import aiofiles # تأكد من تثبيتها: pip install aiofiles
from fastapi import APIRouter, Depends, UploadFile, File # Import File here
from sqlalchemy.orm import Session
# REMOVE 'Path' from the fastapi.params import line above if it exists
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
    # 1. التحقق من حالة التوثيق الحالية لمنع التكرار
    if current_user.verification_status == "pending":
        raise HTTPException(status_code=400, detail="لديك طلب توثيق قيد المراجعة بالفعل.")
    
    if current_user.verification_status == "approved":
        raise HTTPException(status_code=400, detail="حسابك موثق بالفعل.")

    # 2. تحديد المجلد
    UPLOAD_DIR = Path("/tmp/verification")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 3. دالة حفظ الملفات باستخدام async للتعامل الأفضل مع الموارد
    async def save_file(file: UploadFile) -> str:
        # تنظيف اسم الملف من أي مسارات غير آمنة
        filename = f"{current_user.id}_{Path(file.filename).name}"
        file_path = UPLOAD_DIR / filename
        
        async with aiofiles.open(file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # قراءة 1 ميجابايت في المرة
                await buffer.write(content)
        return str(file_path)

    # 4. الحفظ
    try:
        path_to_front = await save_file(id_front)
        path_to_back = await save_file(id_back)
        path_to_selfie = await save_file(selfie_with_id)

        # 5. التحديث في قاعدة البيانات
        new_request = models.VerificationRequest(
            user_id=current_user.id,
            id_front_path=path_to_front,
            id_back_path=path_to_back,
            selfie_with_id_path=path_to_selfie
        )
        
        current_user.verification_status = "pending"
        
        db.add(new_request)
        db.commit()
        
        return {"message": "تم إرسال طلب التوثيق بنجاح، جاري المراجعة."}
        
    except Exception as e:
        # في حال فشل أي عملية حفظ، نقوم بإلغاء التغييرات في قاعدة البيانات
        db.rollback()
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء رفع الملفات: {str(e)}")