from pydantic import Field, field_validator

from app.models import Role
from app.schemas.common import APIModel


class UserCreate(APIModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    role: Role

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: Role | None = None
    is_active: bool | None = None


class UserListItem(APIModel):
    id: int
    username: str
    full_name: str
    role: Role
    is_active: bool
