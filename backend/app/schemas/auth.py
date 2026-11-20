from pydantic import Field

from app.models import Role
from app.schemas.common import APIModel


class LoginRequest(APIModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class UserOut(APIModel):
    id: int
    username: str
    full_name: str
    role: Role
    is_active: bool


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
