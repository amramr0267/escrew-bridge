from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database # Adjust imports based on your folder structure
from ..auth import get_current_user # Adjust path to your auth helper

router = APIRouter()

# Dependency to get DB
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Fetch Active Listings
@router.get("/active-listings")
async def get_active_listings(db: Session = Depends(get_db)):
    listings = db.query(models.Listing).filter(models.Listing.is_active == True).all()
    return listings

# 2. Delete Listing (The Endpoint causing your 404)
@router.delete("/{listing_id}")
async def delete_listing(
    listing_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Fetch the listing
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="العرض غير موجود.")
    
    # Security check: ensure the user is the owner
    if listing.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية حذف هذا العرض.")
    
    # Delete
    db.delete(listing)
    db.commit()
    
    return {"message": "تم حذف العرض بنجاح."}