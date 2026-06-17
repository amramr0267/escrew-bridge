from typing import List

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean 
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base
from backend.app.schemas import ListingResponse, TransactionResponse

# تحديد نوع العملة المحلية
class FiatCurrency(str, enum.Enum):
    SYP = "SYP"
    USD = "USD"

    

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")
    shamcash_number = Column(String, nullable=False)
    phone_number = Column(String, nullable=True) # 🎯 الحقل الجديد الخاص
    is_verified = Column(Boolean, default=False)
    id_card_url = Column(String, nullable=True)
    verification_status = Column(String, default="unverified")
    
    # العلاقات
    listings = relationship("Listing", back_populates="seller")
    transactions_as_buyer = relationship("Transaction", foreign_keys="[Transaction.buyer_id]", back_populates="buyer")
    transactions_as_seller = relationship("Transaction", foreign_keys="[Transaction.seller_id]", back_populates="seller")


class VerificationRequest(Base):
    __tablename__ = "verification_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    id_card_image_path = Column(String, nullable=False) # مسار الصورة على السيرفر
    status = Column(String, default="pending")          # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)


class Listing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"))
    total_amount_usdt = Column(Float, nullable=False)
    remaining_amount_usdt = Column(Float, nullable=False)
    min_amount_usdt = Column(Float, nullable=False)
    exchange_rate = Column(Float, nullable=False)
    fiat_currency = Column(Enum(FiatCurrency), default=FiatCurrency.SYP)
    shamcash_account = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    type = Column(String, nullable=False, default='sell') # 'buy' or 'sell'
    is_verified = Column(Boolean, default=False)
    # العلاقات
    seller = relationship("User", back_populates="listings")
    transactions = relationship("Transaction", back_populates="listing")


# أضف هذه الحقول إلى كلاس Transaction
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"))
    buyer_id = Column(Integer, ForeignKey("users.id"))
    seller_id = Column(Integer, ForeignKey("users.id"))
    locked_usdt_amount = Column(Float, nullable=False)
    fiat_amount_to_pay = Column(Float, nullable=False)
    seller_fee = Column(Float, default=1.0)
    buyer_fee = Column(Float, default=1.0)
    status = Column(String, default="pending")
    txid = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # العلاقات
    listing = relationship("Listing", back_populates="transactions")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="transactions_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="transactions_as_seller")
    buyer_wallet_address = Column(String, nullable=False) # عنوان محفظة المشتري
    completed_at = Column(DateTime, nullable=True)        # تاريخ الإتمام
    release_txid = Column(String, nullable=True)          # معرف التحويل عند الإفراج

class TransactionResponse(BaseModel):
    id: int
    locked_usdt_amount: float
    fiat_amount_to_pay: float
    status: str
    created_at: datetime    
    # We add a computed field in the frontend or backend to show "Buy" or "Sell"

class UserFullProfile(BaseModel):
    user: User # Assuming you have a basic User schema
    listings: List[ListingResponse]
    history: List[TransactionResponse]

    class Config:
        from_attributes = True

class GlobalConfig(Base):
    __tablename__ = "global_config"
    id = Column(Integer, primary_key=True, index=True)
    transaction_timeout_minutes = Column(Integer, default=20) # 🎯 المؤقت الإداري

class PlatformRevenue(Base):
    __tablename__ = "platform_revenue"
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    amount = Column(Float, nullable=False) # المبلغ المحصل (2 USDT)
    created_at = Column(DateTime, default=datetime.utcnow)

    
    
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)