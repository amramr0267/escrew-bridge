from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

import app.models as models
import app.schemas as schemas
from app.database import get_db

# افترضنا أن دوال التشفير وإنشاء التوكن موجودة في مسار الأمان الخاص بك
# إذا كانت في ملف آخر (مثل utils.py) قم بتعديل هذا السطر فقط
from app.services.security import get_password_hash, verify_password, create_access_token

# 🎯 هنا مربط الفرس: تحديد المسار الرئيسي ليطابق الفرونت إند تماماً
router = APIRouter(
    prefix="/api/auth",
    tags=["المصادقة والتسجيل (Authentication)"]
)

# 1️⃣ مسار إنشاء حساب جديد
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # التحقق من أن البريد الإلكتروني غير مستخدم مسبقاً
    existing_user_email = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user_email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل.")

    # التحقق من أن اسم المستخدم غير مستخدم
    existing_user_name = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing_user_name:
        raise HTTPException(status_code=400, detail="اسم المستخدم محجوز، يرجى اختيار اسم آخر.")

    # إنشاء المستخدم الجديد وإضافة رقم الشام كاش الإجباري
    new_user = models.User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        shamcash_number=user_in.shamcash_number, # 🎯 الحقل الجديد تم ربطه هنا
        role="user" # الدور الافتراضي
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء إنشاء الحساب: {str(e)}")


# 2️⃣ مسار تسجيل الدخول (يتوافق مع OAuth2 Form Data)
@router.post("/login", response_model=schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username هنا يمثل ما يدخله المستخدم (ونحن في الفرونت إند نرسل البريد الإلكتروني في هذا الحقل)
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # إذا لم يجده بالبريد، نجرب البحث باسم المستخدم (مرونة للمستخدم)
    if not user:
        user = db.query(models.User).filter(models.User.username == form_data.username).first()

    # التحقق من وجود المستخدم وصحة كلمة المرور
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # إنشاء توكن الدخول
    access_token_expires = timedelta(minutes=60 * 24 * 7) # توكن صالح لمدة أسبوع
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}, 
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": user.role
    }