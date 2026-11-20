from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

# Serialized as a JSON number while kept as Decimal in Python for exact sums.
Quantity = Annotated[Decimal, PlainSerializer(lambda value: float(value), return_type=float, when_used="json")]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str
