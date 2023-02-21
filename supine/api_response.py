from enum import Enum
from typing import Any, Generic, List, TypeVar, Union

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel


Result = TypeVar("Result")


class ApiResponseStatus(str, Enum):
    success = "success"
    error = "error"


class PaginationData(BaseModel):
    start: int = Field(..., description="First record offset", example=0)
    count: int = Field(..., description="Number of records returned", example=1)
    total: Union[int, None] = Field(
        None, description="Total number of records available", example=1
    )

    class Config:
        orm_mode = True


class ApiError(BaseModel):
    detail: str
    status: ApiResponseStatus = ApiResponseStatus.error

    @classmethod
    def from_exc(cls, exc):
        return cls(detail=exc.detail)


class ApiResponse(GenericModel, Generic[Result]):
    status: ApiResponseStatus = ApiResponseStatus.success
    result: Union[Result, None] = None


class PaginatedResponse(ApiResponse, GenericModel, Generic[Result]):
    pagination: Union[PaginationData, None] = None
