import firebase_admin
from firebase_admin import credentials, messaging
import os
from sqlalchemy.orm import Session
from app import models

from fastapi import APIRouter
router = APIRouter()


def initialize_firebase():
    # نقرأ القيم من متغيرات البيئة
    # نستخدم json.loads إذا كانت القيمة مخزنة كـ JSON كامل، أو نقرأ الحقول فرادى
    firebase_config = {
        "type": os.getenv("FIREBASE_TYPE", "service_account"),
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN", "googleapis.com")
    }
    
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

initialize_firebase()

def notify_user(db: Session, user_id: int, title: str, body: str, transaction_id: int = None):
    # 1. حفظ في قاعدة البيانات (In-App)
    new_note = models.Notification(
        user_id=user_id,
        title=title,
        message=body,
        transaction_id=transaction_id
    )
    db.add(new_note)
    db.commit()

    # 2. إرسال Push Notification عبر Firebase
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and user.fcm_token:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=user.fcm_token,
            )
            messaging.send(message)
        except Exception as e:
            print(f"FCM Error: {e}")