from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import app.schemas as schemas
from decimal import Decimal
from app.services.security import get_current_admin, get_current_user  # استيراد حارس الإدارة الصارم

router = APIRouter(
    prefix="/api/admin",
    tags=["لوحة تحكم المسؤول (Admin Panel)"]
)

# 1. جلب العمليات المتنازع عليها فقط (محمي بالأدمن)
@router.get("/disputed-transactions", response_model=list[schemas.TransactionResponse])
async def get_disputed_transactions(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    عرض كافة العمليات المعلقة بسبب نزاع (Dispute) بين البائع والمشتري،
    والتي تتطلب تدخل الأدمن لمراجعة إيصال تحويل الشام كاش يدوياً.
    """
    transactions = db.query(models.Transaction).filter(
        models.Transaction.status == "disputed"
    ).all()
    return transactions


# 2. حسم النزاع والإفراج الإجباري عن الـ USDT لصالح المشتري (محمي بالأدمن)
@router.post("/resolve-dispute/{transaction_id}", response_model=schemas.TransactionResponse)
async def resolve_dispute_force_release(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    حسم النزاع (Force Release):
    يضغط الأدمن على هذا الزر بعد مراجعة إثبات التحويل المحلي، ليقوم السيرفر
    بإجبار النظام على الإفراج عن الـ USDT للمشتري وتحويل الحالة إلى completed.
    """
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة.")

    if transaction.status != "disputed":
        raise HTTPException(
            status_code=400, 
            detail=f"لا يمكن حسم نزاع لمعاملة حالتها الحالية هي: {transaction.status}. يجب أن تكون في حالة نزاع 'disputed' أولاً."
        )

    # حسم النزاع وتغيير الحالة إلى مكتملة
    transaction.status = "completed"
    
    try:
        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ أثناء حسم النزاع وإغلاق المعاملة: {str(e)}")


# 3. رؤية سجل كافة العمليات في المنصة (محمي بالأدمن)
@router.get("/all-transactions", response_model=list[schemas.TransactionResponse])
async def get_all_system_transactions(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    لوحة المراقبة العامة للأدمن:
    عرض كل العمليات الحركية والمالية داخل السيستم أياً كانت حالتها للتدقيق المالي الشامل.
    """
    transactions = db.query(models.Transaction).order_by(models.Transaction.created_at.desc()).all()
    return transactions


# 4. التعديل الذكي لمبلغ المعاملة وإعادة حساب العملة المحلية (محمي بالأدمن)
@router.post("/force-confirm-adjusted/{transaction_id}", response_model=schemas.TransactionResponse)
async def admin_force_confirm_with_adjusted_amount(
    transaction_id: int, 
    actual_amount: float,  # المبلغ الفعلي الواصل للبلوكشين
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    تعديل وقبول يدوي (Adjust & Force Confirm):
    يعدل قيمة المعاملة في الداتابيز (locked_usdt_amount)، ثم يقوم آلياً
    بإعادة حساب المبلغ المحلي المطلوب (fiat_amount_to_pay) بناءً على سعر صرف العرض.
    """
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة.")

    if transaction.status not in ["pending", "disputed"]:
        raise HTTPException(status_code=400, detail=f"لا يمكن تعديل مبلغ معاملة حالتها: {transaction.status}")

    if actual_amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ الفعلي يجب أن يكون أكبر من الصفر.")

    # 🎯 1. جلب العرض الأصلي لمعرفة سعر الصرف
    listing = db.query(models.Listing).filter(models.Listing.id == transaction.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="العرض المرتبط بهذه المعاملة غير موجود.")

    # 🎯 2. تحديث كمية الـ USDT المحجوزة
    transaction.locked_usdt_amount = actual_amount
    
    # 🎯 3. إعادة حساب المبلغ المحلي المطلوب دفعه للمشتري بناءً على السعر الجديد
    transaction.fiat_amount_to_pay = actual_amount * listing.exchange_rate
    
    # تحويل الحالة بقرار إداري لتخطي عقبة المطابقة
    transaction.status = "crypto_confirmed"
    
    try:
        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ أثناء التعديل الإداري للمبلغ: {str(e)}")


# 5. إلغاء المعاملة يدوياً وإعادة الرصيد للبائع (محمي بالأدمن)
@router.post("/force-cancel/{transaction_id}", response_model=schemas.TransactionResponse)
async def admin_force_cancel_transaction(
    transaction_id: int, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    إلغاء إداري إجباري (Force Cancel):
    يقوم الأدمن بإلغاء المعاملة تماماً، والأهم أنه يقوم برد الـ USDT المحجوز
    إلى رصيد العرض الأصلي ليتمكن البائع من بيعه مجدداً.
    """
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة.")

    if transaction.status in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="لا يمكن إلغاء معاملة منتهية بالفعل.")

    # 🎯 جلب العرض وإعادة الرصيد المقتطع إليه
    listing = db.query(models.Listing).filter(models.Listing.id == transaction.listing_id).first()
    if listing:
        listing.remaining_amount_usdt += transaction.locked_usdt_amount
        listing.is_active = True  # إعادة تفعيل العرض في حال كان قد أُغلق بسبب نفاد الكمية

    # تحويل الحالة إلى ملغاة
    transaction.status = "cancelled"
    
    try:
        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ أثناء الإلغاء الإداري وإعادة الرصيد: {str(e)}")


# 6. الميزة الجديدة: تعديل وقت انتهاء الصفقات العام (محمي بالأدمن)
@router.put("/config/timeout")
async def update_global_timeout(
    new_timeout_minutes: int, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    تعديل مهلة الدفع:
    يسمح للأدمن بتحديد الوقت المتاح للمشتري (مثلاً 20 أو 30 دقيقة) قبل أن تلغى الصفقة تلقائياً.
    """
    if new_timeout_minutes < 5:
        raise HTTPException(status_code=400, detail="يجب أن يكون وقت الصفقة 5 دقائق على الأقل.")

    config = db.query(models.GlobalConfig).first()
    if not config:
        config = models.GlobalConfig(transaction_timeout_minutes=new_timeout_minutes)
        db.add(config)
    else:
        config.transaction_timeout_minutes = new_timeout_minutes
        
    try:
        db.commit()
        return {"message": f"تم تحديث وقت انتهاء الصفقات بنجاح ليصبح {new_timeout_minutes} دقيقة.", "new_timeout": new_timeout_minutes}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في حفظ الإعدادات: {str(e)}")
    

@router.get("/stats")
async def get_detailed_stats(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    # 1. إجمالي الأرباح الكلية
    total_revenue = db.query(func.sum(models.PlatformRevenue.amount)).scalar() or 0.0
    
    # 2. أرباح اليوم الحالي فقط
    today = datetime.utcnow().date()
    today_revenue = db.query(func.sum(models.PlatformRevenue.amount)).filter(
        func.date(models.PlatformRevenue.created_at) == today
    ).scalar() or 0.0
    
    # 3. إجمالي العمليات النشطة حالياً (Pending + Disputed)
    active_deals = db.query(models.Transaction).filter(
        models.Transaction.status.in_(["pending", "disputed", "crypto_confirmed"])
    ).count()
    
    # 4. أرباح آخر 30 يوماً (للتحليل الشهري)
    last_month = datetime.utcnow() - timedelta(days=30)
    monthly_revenue = db.query(func.sum(models.PlatformRevenue.amount)).filter(
        models.PlatformRevenue.created_at >= last_month
    ).scalar() or 0.0

    return {
        "summary": {
            "total_all_time_usdt": float(total_revenue),
            "today_revenue_usdt": float(today_revenue),
            "monthly_revenue_usdt": float(monthly_revenue),
            "active_deals_count": active_deals
        }
    }


@router.get("/users/{user_id}", response_model=schemas.AdminUserResponse)
async def get_user_details_for_admin(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="صلاحية الوصول للأدمن فقط.")
        
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
        
    return user # هنا الـ API سيعيد الـ AdminUserResponse التي تحتوي على الرقم