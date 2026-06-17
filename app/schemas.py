from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# ==========================================
# 1️⃣ نماذج المستخدمين (Users)
# ==========================================

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    shamcash_number: str = Field(..., description="رقم الشام كاش مطلوب إجبارياً")

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    shamcash_number: str

    class Config:
        from_attributes = True  # ضرورية لتحويل بيانات SQLAlchemy إلى JSON (في Pydantic v1 تُكتب orm_mode = True)

class UserBasicResponse(BaseModel):
    username: str
    is_verified: bool
    # يمكن إضافة أي حقول أخرى يحتاجها السوق
    class Config:
        from_attributes = True



# ==========================================
# 2️⃣ نماذج العروض في السوق (Listings)
# ==========================================

class ListingCreate(BaseModel):
    total_amount_usdt: float = Field(..., gt=0)
    min_amount_usdt: float = Field(..., gt=0)
    exchange_rate: float = Field(..., gt=0)
    fiat_currency: str
    type: str  # 'buy' or 'sell'

class ListingResponse(BaseModel):
    id: int
    seller_id: int
    total_amount_usdt: float
    remaining_amount_usdt: float
    min_amount_usdt: float
    exchange_rate: float
    fiat_currency: str
    shamcash_account: str
    is_active: bool
    type: str  # 'buy' or 'sell'
    is_verified: bool
    seller_info: Optional[UserBasicResponse] = None
    class Config:
        from_attributes = True


# ==========================================
# 3️⃣ نماذج الصفقات الحية (Transactions)
# ==========================================

class TransactionCreate(BaseModel):
    buy_amount_usdt: float = Field(..., gt=0)
    buyer_wallet_address: str  # تأكد من إضافة هذا الحقل

class TxIDSubmit(BaseModel):
    transaction_id: int
    txid: str = Field(..., description="رقم الحوالة المحلية أو هاش البلوكشين")

class TransactionResponse(BaseModel):
    id: int
    listing_id: int
    buyer_id: Optional[int]
    seller_id: int
    locked_usdt_amount: float
    fiat_amount_to_pay: float
    status: str
    txid: Optional[str]
    created_at: datetime
    expires_at: datetime
    # 🎯 إضافة حقول الرسوم هنا
    seller_fee: float 
    buyer_fee: float 

    class Config:
        from_attributes = True

class AdminUserResponse(UserResponse):
    phone_number: Optional[str] = None # هذا يظهر فقط للأدمن

# ==========================================
# 4️⃣ نماذج تسجيل الدخول (Tokens)
# ==========================================

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str