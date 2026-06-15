import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models

# إعدادات الأمان
SECRET_KEY = os.getenv("JWT_SECRET", "SUPER_SECRET_STRONG_KEY_CHANGE_THIS_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # أسبوع كامل

# 🎯 المسار الموحد للتوكن يطابق المسار الذي عرفناه في auth.py
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# --- محرك التشفير (مطابق للاستدعاءات في auth.py) ---

def get_password_hash(password: str) -> str:
    """تشفير كلمة المرور باستخدام bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """التحقق من كلمة المرور"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- محرك التوكن ---

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """توليد JWT Token مع وقت انتهاء"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- حراس الهوية (Security Dependencies) ---

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """فك تشفير التوكن والتحقق من وجود المستخدم في قاعدة البيانات"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="جلسة العمل غير صالحة أو منتهية.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
        
    return user

async def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """التحقق من صلاحيات الأدمن"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="صلاحيات مرفوضة."
        )
    return current_user

def log_platform_revenue(db: Session, transaction_id: int, amount: float):
    revenue_log = models.PlatformRevenue(
        transaction_id=transaction_id,
        amount=amount
    )
    db.add(revenue_log)
    db.commit()