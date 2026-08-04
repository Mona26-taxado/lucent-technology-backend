from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RequestOtpRequest(BaseModel):
    email: str
    password: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str = Field(min_length=4, max_length=10)


class LoginConfigOut(BaseModel):
    otp_length: int = 6
    # True when backend will show OTP on screen (local / no SMTP)
    dev_otp_mode: bool = False


class OtpSentResponse(BaseModel):
    message: str
    # Only populated in DEBUG when SMTP is not configured — never in production with SMTP
    dev_otp: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
