import dataclasses
import warnings
from functools import cached_property
from itertools import chain
from typing import Callable, List, Type, Union

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, create_model
from sqlalchemy.orm import InstrumentedAttribute, joinedload, Session
from starlette.status import HTTP_404_NOT_FOUND

from supine.api_response import ApiResponse, PaginatedResponse
from supine.filter import Filter


_resource_registry = {}


class ResourceMeta(type):
    def __new__(cls, cls_name, bases, attrs):
        return cls


@dataclasses.dataclass(kw_only=True)
class Resource:
    singular_name: str
    plural_name: str

    orm_class: Type  # orm base model
    model: Type[BaseModel]  # a fastapi response_model for a single response
    create_params: Type[BaseModel] = None  # a pydantic model for create/POST parameters
    update_params: Type[
        BaseModel
    ] = None  # a pydantic model for update/PATCH parameters

    query_filter: Union[
        Type[Filter], Callable[[], None]
    ] = lambda: None  # lambda: None for no filter
    expansions: List[Union["Resource", str]] = dataclasses.field(
        default_factory=list
    )  # a list of Resources this Resource may reference

    def __post_init__(self):
        self.register()

    def register(self):
        resource_key = self.plural_name
        if resource_key in _resource_registry:
            warnings.warn(f"Resource {resource_key} already registered -- overwriting")
        _resource_registry[resource_key] = self

    @cached_property
    def result(self):
        model = create_model(
            self.model.__name__ + "Result",
            __base__=BaseModel,
            **{
                self.singular_name: (self.model, ...),
                **{
                    exp.plural_name: (List[exp.model], None)
                    for exp in self.runtime_expansions
                },
            },
        )
        model.__doc__ = self.model.__doc__
        return ApiResponse[model]

    @cached_property
    def list_result(self):
        model = create_model(
            self.model.__name__ + "ListResult",
            __base__=BaseModel,
            **{self.plural_name: (List[self.model], [])},
        )
        return PaginatedResponse[model]

    @cached_property
    def runtime_expansions(self):
        return [
            exp if isinstance(exp, Resource) else _resource_registry[exp]
            for exp in self.expansions
        ]
