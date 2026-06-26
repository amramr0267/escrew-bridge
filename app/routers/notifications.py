from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# 1. جلب تنبيهات المستخدم
@router.get("/")
async def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).all()

# 2. تأشير تنبيه كمقروء
@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    note = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="التنبيه غير موجود")
    
    note.is_read = True
    db.commit()
    return {"message": "تم تحديث التنبيه"}


def create_notification(db: Session, user_id: int, message: str, transaction_id: int = None):
    new_note = models.Notification(
        user_id=user_id,
        message=message,
        transaction_id=transaction_id
    )
    db.add(new_note)
    db.commit()