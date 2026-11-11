from pydantic import BaseModel, Field, field_validator
import re

class NewsletterSubscribeRequest(BaseModel):
    email: str = Field(..., description="Subscriber email address")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
            raise ValueError("Invalid email format")
        return s

class NewsletterSubscribeResponse(BaseModel):
    ok: bool = True
    email: str
    message: str = "Successfully subscribed to Cloud-Loop opportunity alerts."
