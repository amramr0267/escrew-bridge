from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.security import get_current_user
import requests , json


router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# 1. جلب تنبيهات المستخدم
@router.get("/")
async def get_notifications(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # جلب الإشعارات بترتيب تنازلي مع Pagination
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).offset(offset).limit(limit).all()
    
    return notifications

@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # تحديث كل الإشعارات غير المقروءة لهذا المستخدم
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    return {"message": "تم تحديث جميع الإشعارات كمقروءة"}


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

def send_notification(db: Session, user_id: int, message: str, transaction_id: int = None, title: str = "تنبيه من المنصة"):
    # 1. حفظ الإشعار في قاعدة البيانات (In-App)
    new_note = models.Notification(
        user_id=user_id,
        message=message,
        transaction_id=transaction_id,
        title=title
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)

    # 2. إرسال الإشعار الخارجي (Push Notification) عبر Expo
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user and user.push_token:
        try:
            # تجهيز الطلب لـ Expo Push API
            url = "https://exp.host/--/api/v2/push/send"
            payload = {
                "to": user.push_token,
                "title": title,
                "body": message,
                "data": {
                    "transaction_id": str(transaction_id) if transaction_id else ""
                }
            }
            
            # إرسال الطلب
            response = requests.post(url, json=payload)
            response.raise_for_status() # للتأكد من نجاح الطلب
            
        except Exception as e:
            # تسجيل الخطأ مع الاستمرار في عمل التطبيق
            print(f"فشل إرسال Push Notification للمستخدم {user_id}: {e}")






def send_push_notification(user_token: str, title: str, body: str):
    # الـ Token الخاص بـ Expo يبدأ دائماً بـ "ExponentPushToken[...]"
    url = "https://exp.host/--/api/v2/push/send"
    payload = {
        "to": user_token,
        "title": title,
        "body": body,
        "data": {"someData": "goes here"}
    }
    
    response = requests.post(url, json=payload)
    return response.json()