from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from src.security import validate_password_strength


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserRegisterResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ActivationRequest(BaseModel):
    email: EmailStr
    token: str


class ResendActivationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str
