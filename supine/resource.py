import warnings
from datetime import datetime
from functools import cached_property
from typing import List, Type, Union

from pydantic import BaseModel, create_model

from supine.api_response import ApiResponse, PaginatedResponse
from supine.filter import Filter

_resource_registry = {}


class Resource:
    def __init__(
        self,
        *,
        singular_name: str,  # string name of a single instance of this Resource (example: 'territory')
        plural_name: str,  # string name of plural instances of this Resource (example: 'territories')
        orm_class: Type,  # orm base model
        model: Type[BaseModel],  # a fastapi response_model for a single response
        create_params: Type[BaseModel] = None,  # for create/POST parameters
        update_params: Type[BaseModel] = None,  # for update/PATCH parameters
        query_filter: Union[Type[Filter], None] = None,
        expansions: List[Union["Resource", str]] = None,
        etag_attr: str = None,
        last_modified_attr: str = None,
        max_age: int = 0,  # max cache age in seconds
    ):
        """
        A Resource ties together orm, de/serialization, and parameter models.
        SupineRouter can use this resource to generate CRUD routes

        :param singular_name: example 'territory', used to generate url paths and messages for this resource
            will be registered in a dict, so must be unique among all Resources in this project

        :param plural_name: example 'territories' used to generate messages and
            to access relationships to this resource

        :param orm_class: the SQLAlchemy database model for this resource

        :param model: the pydantic serialization model for this resource (pydantic.parse_obj_as(model, orm_class())

        :param create_params: pydantic model to create an orm_class instance as in orm_class(**params)

        :param update_params: pydantic model to update an orm_class instance as in setattr(instance, param, val)

        :param query_filter: Filter model -- dependency injected for getting a list of this resource, then
          used to filter the sqlalchemy query and/or query results

        :param expansions: list of other Resources accessible on orm_class instances as getattr(instance, plural_name)
          can be provided as strings corresponding to the singular_name to avoid circular reference problems

        :param etag_attr: str name of an attribute on orm_class that returns an etag (example a rowversion()
            from SQL Server or a uuid on). Used to determine if client-side cache is fresh. Only get-by-key
            routes allow caching.

        :param last_modified_attr: str name of an attribute on orm_class that returns a datetime representing
            its last update time. Used to determine if client-side cache is fresh. Only get-by-key
            routes allow caching.

        :param max_age: number of seconds to indicate to client as the maximum amount of time to
            cache this resource. Only get-by-key routes allow caching.
        """
        self.singular_name = singular_name
        self.plural_name = plural_name
        self.orm_class = orm_class
        self.model = model
        self.create_params = create_params
        self.update_params = update_params
        self.query_filter = query_filter or null_filter
        self.expansions = expansions or []
        self.etag_attr = etag_attr
        self.last_modified_attr = last_modified_attr
        self.max_age = max_age
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
        """
        lazy-evaluates strings in the expansion list by looking them up in the resource registry
        """
        return [
            exp if isinstance(exp, Resource) else _resource_registry[exp]
            for exp in self.expansions
        ]

    def get_expansion_dict(self, orm_instance) -> dict[str, list]:
        """
        given a Resource definition and an ORM instance, return a dict of
        expansion.plural_name to matching orm attribute
        """
        return {
            expansion.plural_name: getattr(orm_instance, expansion.plural_name)
            for expansion in self.runtime_expansions
        }

    def etag(self, orm_instance) -> str:
        """return resource etag given an orm_class instance"""
        if self.etag_attr is None:
            return None
        return getattr(orm_instance, self.etag_attr)

    def last_modified(self, orm_instance) -> datetime:
        """return resource last modified datetime given an orm_class instance"""
        if self.last_modified_attr is None:
            return None
        return getattr(orm_instance, self.last_modified_attr)


def null_filter():
    """Used where a Filter is expected but no filter is necessary"""
    return None
