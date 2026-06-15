from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean 
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base

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
    shamcash_number = Column(String, nullable=False) # 🎯 الحقل الجديد الإجباري

class Listing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"))
    total_amount_usdt = Column(Float, nullable=False)
    remaining_amount_usdt = Column(Float, nullable=False) # 🎯 المبلغ المتبقي للتداول الجزئي
    min_amount_usdt = Column(Float, nullable=False)       # 🎯 الحد الأدنى للبيع
    exchange_rate = Column(Float, nullable=False)         # 🎯 سعر الصرف المخصص
    fiat_currency = Column(Enum(FiatCurrency), default=FiatCurrency.SYP) # 🎯 نوع العملة
    shamcash_account = Column(String, nullable=False)     # يُسحب تلقائياً من البائع
    is_active = Column(Boolean, default=True)

# أضف هذه الحقول إلى كلاس Transaction
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"))
    buyer_id = Column(Integer, ForeignKey("users.id"))
    seller_id = Column(Integer, ForeignKey("users.id"))
    
    # الكميات الأساسية
    locked_usdt_amount = Column(Float, nullable=False)    # الـ 1000 USDT (أصل الصفقة)
    fiat_amount_to_pay = Column(Float, nullable=False)
    
    # 🎯 حقول نظام الرسوم الجديد
    seller_fee = Column(Float, default=1.0)           # عمولة البائع (تُدفع عند الإنشاء)
    buyer_fee = Column(Float, default=1.0)            # عمولة المشتري (تُخصم عند الإفراج)
    
    status = Column(String, default="pending")
    txid = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)        # 🎯 وقت انتهاء الصفقة

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