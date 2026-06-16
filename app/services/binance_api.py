import os
import logging
from binance.spot import Spot
from binance.error import ClientError

# إعداد الـ Logger لمراقبة الأخطاء في Vercel Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# جلب الإعدادات من متغيرات بيئة Vercel
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_MODE = os.getenv("BINANCE_MODE", "test")

async def verify_txid_on_binance(txid: str, expected_amount: float) -> bool:
    """
    الاتصال الفعلي بـ Binance API للتحقق من وصول الحوالة ومطابقة المبلغ.
    """
    
    # 1. وضع المحاكاة للتطوير المحلي (Test Mode)
    if BINANCE_MODE == "test":
        logger.info(f"[Binance Mock] تم قبول الـ TxID: {txid} تجريبياً.")
        return True

    # 2. التحقق من وجود المفاتيح قبل الاتصال
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.error("[Binance API] مفاتيح API مفقودة في إعدادات النظام.")
        return False

    try:
        # 3. تهيئة العميل (Spot Client)
        client = Spot(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
        
        # 4. جلب سجل الإيداعات (Status 1 = Successful)
        # نقوم بجلب آخر 50 عملية لتغطية فترة انتظار المستخدم
        deposit_history = client.deposit_history(coin="USDT", status=1, limit=50)
        
        if not deposit_history:
            logger.warning("[Binance API] لا توجد إيداعات ناجحة لعملة USDT.")
            return False

        # 5. مطابقة المعاملة
        for deposit in deposit_history:
            if deposit.get("txId") == txid:
                blockchain_amount = float(deposit.get("amount", 0))
                
                # مطابقة المبلغ (مع السماح بفرق تقريب بسيط 0.001)
                if abs(blockchain_amount - expected_amount) < 0.001:
                    logger.info(f"[Binance API] نجاح التحقق! المبلغ: {blockchain_amount} USDT.")
                    return True
                else:
                    logger.warning(f"[Binance API] المبلغ غير مطابق! المطلوب: {expected_amount}, الواصل: {blockchain_amount}.")
                    return False
        
        logger.warning(f"[Binance API] لم يتم العثور على الـ TxID: {txid} في سجلاتك.")
        return False

    except ClientError as e:
        logger.error(f"[Binance API ClientError] {e.error_message}")
        return False
    except Exception as e:
        logger.error(f"[Binance API General Error] {str(e)}")
        return False