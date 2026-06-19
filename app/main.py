from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
# استيراد نظيف ومرة واحدة فقط لكل ملف
from app.routers import transactions, admin, auth , users, listings

from app.routers import notifications # تأكد من المسار الصحيح

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="بوابة الضمان الرقمي (Escrow Bridge API)",
    description="نظام وسيط آمن للتحويل بين عملة USDT الرقمية وشبكة ShamCash المحلية في سوريا مع نظام عمولات ديناميكي.",
    version="0.1.0"
)
origins = [
    "http://localhost:5173",  # منفذ Vite الافتراضي
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ربط الـ Routers مرة واحدة فقط
# main.py
app.include_router(auth.router) # أضفت الـ prefix هنا ليتوافق مع security.py
app.include_router(transactions.router, prefix="/api/transactions")
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(listings.router, prefix="/api/listings")
app.include_router(notifications.router)


@app.get("/", tags=["الفحص العام"])
async def root():
    return {
        "status": "online",
        "project": "بوابة الضمان الرقمي"
    }