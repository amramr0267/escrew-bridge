from fastapi import APIRouter

router = APIRouter(prefix="/api/support", tags=["Support"])

@router.get("/contact-info")
async def get_contact_info():
    return {
        "whatsapp": "https://wa.me/905510629877",  # استبدل الرقم برقم الدعم الفني
        "telegram": "https://t.me/Alhabeb1990", # استبدل باليوزر الخاص بك
        "email": "support@darkwire.com"
    }