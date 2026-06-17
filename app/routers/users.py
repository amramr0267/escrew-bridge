from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import app.schemas as schemas
from app.services.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/me", response_model=schemas.UserResponse)
def get_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/update-phone")
async def update_phone_number(
    new_phone: str, # أو استخدم Schema
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.phone_number = new_phone
    db.commit()
    return {"message": "تم تحديث رقم الهاتف بنجاح."}

@router.get("/me/full-data")
async def get_user_full_data(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Stats
    trades = db.query(models.Transaction).filter(
        ((models.Transaction.buyer_id == current_user.id) | (models.Transaction.seller_id == current_user.id)),
        models.Transaction.status == 'completed'
    ).all()
    
    # 2. My Listings (Active offers created by me)
    my_listings = db.query(models.Listing).filter(models.Listing.seller_id == current_user.id).all()
    
    # 3. History (All trades involving user)
    my_history = db.query(models.Transaction).filter(
        (models.Transaction.buyer_id == current_user.id) | (models.Transaction.seller_id == current_user.id)
    ).order_by(models.Transaction.created_at.desc()).all()
    
    return {
        "stats": {"completed_trades": len(trades), "total_volume": sum([t.locked_usdt_amount for t in trades])},
        "my_listings": my_listings,
        "history": my_history
    }