from fastapi import APIRouter, Depends
from app.core.security import verify_internal_api_key
from app.schemas.newsletter import NewsletterSubscribeRequest, NewsletterSubscribeResponse
from app.repositories.newsletter_repository import newsletter_repo

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])

@router.post("", response_model=NewsletterSubscribeResponse)
def subscribe_newsletter(
    payload: NewsletterSubscribeRequest,
    _auth: bool = Depends(verify_internal_api_key),
):
    """
    POST /api/v1/newsletter
    Records subscriber email into CLOUDLOOP.NEWSLETTER_SUBSCRIBERS with MERGE duplicate handling.
    """
    newsletter_repo.subscribe(payload.email)
    return NewsletterSubscribeResponse(
        ok=True,
        email=payload.email,
        message="Successfully subscribed to Cloud-Loop opportunity updates.",
    )
