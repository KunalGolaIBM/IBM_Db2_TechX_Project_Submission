from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.base import get_db
from backend.app.models.entities import User, TrustedContact
from backend.app.schemas.safety_schemas import TrustedContactCreate, TrustedContactResponse
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/trusted-contacts", tags=["Trusted Contacts"])

@router.get("", response_model=List[TrustedContactResponse])
def get_trusted_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contacts = db.query(TrustedContact).filter(TrustedContact.user_id == current_user.id).all()
    return contacts

@router.post("", response_model=TrustedContactResponse, status_code=status.HTTP_201_CREATED)
def add_trusted_contact(
    req: TrustedContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contact = TrustedContact(
        user_id=current_user.id,
        name=req.name,
        relationship=req.relationship,
        phone=req.phone,
        email=req.email,
        can_receive_sos=req.can_receive_sos,
        can_track_location=req.can_track_location
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trusted_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contact = db.query(TrustedContact).filter(
        TrustedContact.id == contact_id,
        TrustedContact.user_id == current_user.id
    ).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trusted contact not found.")
    
    db.delete(contact)
    db.commit()
    return None
