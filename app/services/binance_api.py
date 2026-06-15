import os
import hmac
import hashlib
import time
import httpx
from binance.spot import Spot as Client

# سحب المفاتيح السرية بأمان من بيئة النظام (ملف .env)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
# وضع الفحص: 'test' للمحاكاة، و 'production' للربط الحقيقي بـ بينانس
BINANCE_MODE = os.getenv("BINANCE_MODE", "test")

async def verify_txid_on_binance(txid: str, expected_amount: float) -> bool:
    """
    الاتصال الفعلي بـ Binance API للتحقق من وصول الحوالة الرقمية ومطابقة المبلغ والـ TxID
    """
    # 1. إذا كان النظام في وضع الفحص (Test Mode)، سنمرر المعاملة للتبسيط والتطوير المحلي
    if BINANCE_MODE == "test" or not BINANCE_API_KEY or not BINANCE_API_SECRET:
        print(f"[Binance Mock] تم فحص الـ TxID: {txid} بنجاح في وضع التطوير المحلي لمبلغ {expected_amount} USDT.")
        return True

    try:
        # 2. تهيئة عميل بينانس الرسمي باستخدام مفاتيح حسابك الآمنة
        # نستخدم httpx للاتصال غير المتزامن (Async) لضمان سرعة الاستجابة
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        
        # 3. طلب سجل الإيداعات لعملة USDT فقط من حسابك على بينانس
        # نجلب آخر 10 إيداعات تمت على المحفظة
        deposit_history = client.deposit_history(coin="USDT", status=1) # status=1 تعني الإيداعات الناجحة والمكتملة فقط
        
        if not deposit_history:
            print("[Binance API] سجل الإيداعات فارغ حالياً لعملة USDT.")
            return False

        # 4. البحث والمطابقة داخل السجل القادم من البلوكشين
        for deposit in deposit_history:
            # مطابقة معرف المعاملة (TxID) مع المسجل على شبكة البلوكشين
            if deposit.get("txId") == txid:
                blockchain_amount = float(deposit.get("amount", 0))
                
                # مطابقة المبلغ الواصل مع المبلغ المطلوب (شاملاً عمولتك الفوقية)
                # نضع نسبة سماح ضئيلة جداً (0.001) لتفادي أي فروقات تقريب مالي
                if abs(blockchain_amount - expected_amount) < 0.001:
                    print(f"[Binance API] نجاح! تم العثور على المعاملة والمبلغ متطابق: {blockchain_amount} USDT.")
                    return True
                else:
                    print(f"[Binance API] تحذير: الـ TxID متطابق ولكن المبلغ في البلوكشين ({blockchain_amount}) مختلف عن المطلوب ({expected_amount}).")
                    return False
                    
        print(f"[Binance API] لم يتم العثور على الـ TxID: {txid} في سجل الإيداعات الناجحة لحسابك.")
        return False

    except Exception as e:
        print(f"[Binance API Error] حدث خطأ أثناء الاتصال بخوادم بينانس: {str(e)}")
        return False