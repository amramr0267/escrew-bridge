import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# شحن المتغيرات البيئية من ملف .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# حماية وتأكيد: إذا كان الرابط فارغاً أو يستخدم المحرك القديم، يتم تعديله تلقائياً
if not DATABASE_URL:
    # رابط احتياطي افتراضي لتشغيل النظام فوراً في بيئة التطوير المحلية
    DATABASE_URL = "postgresql+psycopg://postgres:Amrhfz11@localhost:5432/escrow_db"
elif DATABASE_URL.startswith("postgresql://"):
    # استبدال المحرك القديم بالمحرك الجديد المتاح في جهازك
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# إنشاء محرك الاتصال بقاعدة البيانات باستخدام المحرك الصحيح مجبراً
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()