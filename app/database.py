import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# نجلب الرابط كما هو
DATABASE_URL = os.getenv("DATABASE_URL")

# إذا لم نجد رابطاً، نستخدم رابط التطوير المحلي (مع التأكد من استخدام psycopg2)
if not DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg2://postgres:Amrhfz11@localhost:5432/escrow_db"
else:
    # نقوم بعمل Replace لأي صيغة سابقة لضمان استخدام psycopg2 دائماً
    # نستبدل postgresql:// أو postgresql+psycopg:// بـ postgresql+psycopg2://
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg2://")
    if not DATABASE_URL.startswith("postgresql+psycopg2://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

# إنشاء المحرك مع إجبار استخدام psycopg2
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()