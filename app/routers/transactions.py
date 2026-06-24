from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta, timezone
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.binance_api import execute_binance_withdrawal, verify_txid_on_binance
from app.services.security import get_current_user, log_platform_revenue  
from decimal import Decimal
import math  
from app.routers.notifications import create_notification

router = APIRouter(prefix="", tags=["Transactions"]) 

# 1️⃣ البائع ينشئ عرض بيع USDT في السوق (Listing)
@router.post("/create", response_model=schemas.ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_p2p_listing(
    listing_in: schemas.ListingCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    إنشاء عرض بيع جديد:
    يسحب رقم الشام كاش تلقائياً من البروفايل، ويحدد سعر الصرف ونوع العملة المحلية.
    """
    if listing_in.total_amount_usdt <= 0 or listing_in.min_amount_usdt <= 0:
        raise HTTPException(status_code=400, detail="يجب أن تكون المبالغ أكبر من الصفر.")
        
    if listing_in.min_amount_usdt > listing_in.total_amount_usdt:
        raise HTTPException(status_code=400, detail="الحد الأدنى للبيع لا يمكن أن يكون أكبر من المبلغ الإجمالي.")

    # 🎯 سحب رقم الشام كاش من بروفايل المستخدم تلقائياً
    if not current_user.shamcash_number:
        raise HTTPException(status_code=400, detail="يرجى تحديث ملفك الشخصي وإضافة رقم الشام كاش قبل إنشاء عرض.")

    new_listing = models.Listing(
        seller_id=current_user.id,
        type=listing_in.type,  # 🎯 Mapping the new field        
        total_amount_usdt=listing_in.total_amount_usdt,
        remaining_amount_usdt=listing_in.total_amount_usdt, # يبدأ الرصيد كاملاً
        min_amount_usdt=listing_in.min_amount_usdt,
        exchange_rate=listing_in.exchange_rate,
        fiat_currency=listing_in.fiat_currency,
        shamcash_account=current_user.shamcash_number, # حقن تلقائي
        is_active=True,
        is_verified=current_user.is_verified # Assuming user model has this
    )
    
    try:
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)
        return new_listing
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ أثناء إنشاء العرض: {str(e)}")


# 2️⃣ المشتري يوافق على شراء جزء (أو كل) العرض ويقفل الضمان
@router.post("/match/{listing_id}", response_model=schemas.TransactionResponse)
async def match_buyer_to_listing(
    listing_id: int, 
    order: schemas.TransactionCreate, # يحتوي على buy_amount_usdt
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    المطابقة الجزئية:
    يتم التحقق من الكمية المطلوبة، حجزها، حساب القيمة المحلية، وبدء المؤقت التنازلي.
    """
    listing = db.query(models.Listing).filter(
        models.Listing.id == listing_id,
        models.Listing.is_active == True
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="العرض غير متاح أو نفدت كميته.")

    if listing.seller_id == current_user.id:
        raise HTTPException(status_code=400, detail="لا يمكنك الشراء من العرض الخاص بك!")

    # 🎯 التحقق من حدود الشراء (Min / Max)
    if order.buy_amount_usdt < listing.min_amount_usdt:
        raise HTTPException(status_code=400, detail=f"الحد الأدنى للشراء من هذا العرض هو {listing.min_amount_usdt} USDT")
        
    if order.buy_amount_usdt > listing.remaining_amount_usdt:
        raise HTTPException(status_code=400, detail="الكمية المطلوبة تتجاوز الرصيد المتبقي المتاح في العرض.")

    # 🎯 خصم الرصيد وتحديث حالة العرض
    listing.remaining_amount_usdt -= order.buy_amount_usdt
    if listing.remaining_amount_usdt < listing.min_amount_usdt:
        listing.is_active = False # إغلاق العرض إذا أصبح المتبقي أقل من الحد الأدنى

    # 🎯 جلب المؤقت الإداري العام (مثلاً 20 دقيقة)
    config = db.query(models.GlobalConfig).first()
    timeout = config.transaction_timeout_minutes if config else 20
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=timeout)

    # 🎯 حساب القيمة المحلية المطلوبة بناءً على سعر الصرف
    fiat_to_pay = float(order.buy_amount_usdt) * listing.exchange_rate

    # إنشاء الصفقة الحية المستقلة
    new_tx = models.Transaction(
        listing_id=listing.id,
        buyer_id=current_user.id,
        seller_id=listing.seller_id,
        locked_usdt_amount=order.buy_amount_usdt,
        fiat_amount_to_pay=fiat_to_pay,
        buyer_wallet_address = getattr(order, 'buyer_wallet_address', 'N/A'),
        expires_at=expiry_time,
        system_wallet_address="TQ8uA... (ضع عنوان محفظتك هنا أو اجلبه من إعدادات النظام)",
        status="pending_deposit"
    )
        
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx


# 3️⃣ مسار جلب السجل المالي لصفحة البروفايل
# أضف هذا المسار داخل ملف transactions.py
@router.get("/my-history", response_model=List[schemas.TransactionResponse])
def get_my_transaction_history(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """سحب كافة الصفقات التي شارك فيها المتداول الحالي."""
    history = db.query(models.Transaction).filter(
        (models.Transaction.seller_id == current_user.id) | 
        (models.Transaction.buyer_id == current_user.id)
    ).order_by(models.Transaction.created_at.desc()).all()
    
    return history


# 4️⃣ مسار جلب كافة عمليات السوق العام (العروض النشطة فقط)
@router.get("/all", response_model=List[schemas.ListingResponse])
async def get_all_active_listings(db: Session = Depends(get_db)):
    results = db.query(models.Listing, models.User).join(
        models.User, models.Listing.seller_id == models.User.id
    ).filter(models.Listing.is_active == True).all()
    
    output = []
    for listing, user in results:
        # Convert SQLAlchemy model to dict
        data = listing.__dict__.copy()
        # Manually attach the seller info
        data["seller_info"] = {
            "username": user.username,
            "is_verified": user.is_verified
        }
        output.append(data)
    
    return output

# 5️⃣ مسار جلب تفاصيل صفقة محددة لدخول غرفة الضمان
@router.get("/{id}", response_model=schemas.TransactionResponse)
def get_transaction_by_id(
    id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    # Use joinedload to include user data in the query
    tx = db.query(models.Transaction).options(
        joinedload(models.Transaction.buyer),
        joinedload(models.Transaction.seller)
    ).filter(models.Transaction.id == id).first()
    
    if not tx:
        raise HTTPException(status_code=404, detail="عذراً، هذه الصفقة غير موجودة في النظام.")
    
    if current_user.role != "admin" and current_user.id != tx.seller_id and current_user.id != tx.buyer_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول غرفة هذه الصفقة.")
        
    return tx


# 6️⃣ إرفاق رمز تحويل البلوكشين أو إيصال الحوالة المحلية
@router.post("/submit-txid")
async def submit_txid(payload: schemas.TxIDSubmit, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == payload.transaction_id).first()
    
    # Validation
    fee = calculate_fee(tx.locked_usdt_amount)
    required_amount = tx.locked_usdt_amount + fee
    
    # 🎯 Verify on Binance (or your system wallet)
    is_valid = await verify_txid_on_binance(payload.txid, required_amount)
    if not is_valid:
        raise HTTPException(status_code=400, detail="المبلغ المحول غير مطابق أو الـ TXID غير صالح.")
        
    tx.txid = payload.txid
    tx.status = "crypto_received" # Updated status
    tx.buyer_fee = fee
    db.commit()
    return tx


@router.post("/release-crypto/{transaction_id}")
async def release_crypto_to_buyer(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. التحقق من الصفقة
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id
    ).first()

    # حماية: التأكد أن المستخدم هو البائع الأصلي للصفقة
    if not transaction or transaction.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية الإفراج عن هذه الصفقة.")

    # حماية: التأكد أن الحالة تسمح بالإفراج
    if transaction.status != "payment_proof_submitted":
        raise HTTPException(status_code=400, detail="لا يمكن الإفراج: الحالة الحالية لا تسمح بذلك.")

    # 2. تنفيذ التحويل من محفظة التطبيق (App Wallet)
    try:
        # خصم الرسوم (Fee) من المبلغ الإجمالي
        total_amount = float(transaction.locked_usdt_amount)
        fee = total_amount * 0.01  # عمولة 1%
        release_amount = total_amount - fee

        # استدعاء دالة التحويل (التي أنشأناها مسبقاً)
        withdrawal_response = await execute_binance_withdrawal(
            address=transaction.buyer_wallet_address,
            amount=release_amount
        )
        
        # 3. تحديث قاعدة البيانات عند نجاح التحويل فقط
        transaction.status = "completed"
        transaction.release_txid = withdrawal_response.get('id')
        transaction.completed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(transaction)
        
        # 4. تسجيل الأرباح في جدول الإيرادات
        log_platform_revenue(db, transaction.id, fee)
        
        return {"message": "تم الإفراج عن الأموال بنجاح للمشتري", "txid": transaction.release_txid}

    except Exception as e:
        db.rollback() # تراجع عن أي تغيير في القاعدة إذا فشل التحويل
        raise HTTPException(status_code=500, detail=f"فشل الإفراج التلقائي: {str(e)}")


def calculate_fee(amount: float) -> float:
    # 0-500 = 0.5, 501-1000 = 1.0, etc.
    return (math.ceil(amount / 500)) * 0.5

# 8️⃣ زر المشتري لفتح نزاع/اعتراض رسمي في حال مماطلة البائع
@router.post("/raise-dispute/{transaction_id}", response_model=schemas.TransactionResponse)
async def raise_transaction_dispute(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. البحث عن المعاملة (تعديل: السماح بفتح النزاع في حالتي pending أو crypto_confirmed)
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.status.in_(["pending", "crypto_confirmed"]) 
    ).first()

    if not transaction:
        raise HTTPException(status_code=400, detail="لا يمكن فتح نزاع: المعاملة إما مكتملة، ملغاة، أو قيد النزاع بالفعل.")

    # 2. التحقق من أن المستخدم طرف في العملية (سواء كان بائعاً أو مشترياً)
    if transaction.buyer_id != current_user.id and transaction.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا يمكنك رفع نزاع على معاملة لست طرفاً فيها.")

    # 3. تحديث الحالة
    transaction.status = "disputed"
    
    try:
        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ أثناء فتح النزاع الإداري: {str(e)}")

# In routers/transactions.py
@router.get("/my-history", response_model=List[schemas.TransactionResponse])
async def get_my_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # This fetches all transactions where the user was either the buyer or the seller
    history = db.query(models.Transaction).filter(
        (models.Transaction.buyer_id == current_user.id) | 
        (models.Transaction.seller_id == current_user.id)
    ).order_by(models.Transaction.created_at.desc()).all()
    
    return history

@router.post("/cleanup-expired")
async def cleanup_expired_transactions(db: Session = Depends(get_db)):
    expiry_threshold = datetime.utcnow() - timedelta(hours=24)
    
    # Delete transactions older than 24h that are still 'pending'
    expired_txs = db.query(models.Transaction).filter(
        models.Transaction.status == "pending",
        models.Transaction.created_at < expiry_threshold
    ).delete()
    
    db.commit()
    return {"message": f"تم حذف {expired_txs} صفقة منتهية الصلاحية."}


@router.post("/cancel-expired/{transaction_id}")
async def cancel_expired_transaction(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    tx = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.status == "pending_deposit"
    ).first()

    if not tx:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة أو لا يمكن إلغاؤها.")

    # التحقق من أن الوقت قد انتهى فعلاً في السيرفر
    if datetime.utcnow() < tx.expires_at:
        raise HTTPException(status_code=400, detail="لا يزال هناك وقت متبقي للصفقة.")

    # إلغاء الصفقة وإعادة تفعيل العرض (Listing) إذا كان متاحاً
    tx.status = "cancelled"
    listing = db.query(models.Listing).filter(models.Listing.id == tx.listing_id).first()
    if listing:
        listing.remaining_amount_usdt += tx.locked_usdt_amount
        listing.is_active = True
        
    db.commit()
    return {"message": "تم إلغاء الصفقة بنجاح بسبب انتهاء الوقت."}