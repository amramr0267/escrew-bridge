from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# 🎯 الخدمة: دالة لإنشاء إشعار (تُستخدم داخل دوال المعاملات الأخرى)
def create_notification(db: Session, user_id: int, transaction_id: int, message: str):
    new_notif = models.Notification(
        user_id=user_id,
        transaction_id=transaction_id,
        message=message
    )
    db.add(new_notif)
    db.commit()

# 🎯 المسار: جلب إشعارات المستخدم الحالي
@router.get("/my-notifications")
async def get_my_notifications(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).all()

# 🎯 المسار: تمييز إشعار كمقروء
@router.post("/read/{notification_id}")
async def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notif:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
        
    notif.is_read = True
    db.commit()
    return {"status": "success"}