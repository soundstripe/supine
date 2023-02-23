import warnings
from datetime import datetime
from functools import cached_property
from itertools import chain
from typing import List, Type, Union

from pydantic import BaseModel, create_model
from sqlalchemy.orm import InstrumentedAttribute, joinedload

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

        :param plural_name: example 'territories' used to generate messages and
            to access relationships to this resource. will be registered in a dict, so must be unique among
            all Resources in this project

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
        self._expansions = expansions or []
        self.etag_attr = etag_attr
        self.last_modified_attr = last_modified_attr
        self.max_age = max_age
        self._register()

    @cached_property
    def result(self):
        """
        An APIResponse wrapping a single `.model` to be used as a response_model for FastAPI routes

        Example JSON response for a 'document' Resource
        (in this example, .expansions has a single additional resource, w/plural name `document_categories`)
        {
            'status': 'success',
            'result': {
                'document': {...},
                'document_categories': [
                    {...},
                    {...},
                ]
            }
        }
        """
        model = create_model(
            self.model.__name__ + "Result",
            __base__=BaseModel,
            **{
                self.singular_name: (self.model, ...),
                **{exp.plural_name: (List[exp.model], None) for exp in self.expansions},
            },
        )
        model.__doc__ = self.model.__doc__
        return ApiResponse[model]

    @cached_property
    def list_result(self):
        """
        A PaginatedResponse wrapping a list of `.model`s to be used as a response_model for FastAPI routes

        Example JSON response for a list of 'document' Resources
        {
            'status': 'success',
            'result': {
                'documents': [{...}, {...}, ...]
            },
            'pagination': {
                'start': 0,
                'count': 100,
                'total': 2726
            }
        }
        """
        model = create_model(
            self.model.__name__ + "ListResult",
            __base__=BaseModel,
            **{self.plural_name: (List[self.model], [])},
        )
        return PaginatedResponse[model]

    @cached_property
    def expansions(self):
        """
        Returns the list of Resource objects that can be expanded on this Resource

        lazy-evaluates strings in the expansion list by looking them up in the resource registry
        """
        return [
            exp if isinstance(exp, Resource) else _resource_registry[exp]
            for exp in self._expansions
        ]

    def get_expansion_dict(self, orm_instance) -> dict[str, list]:
        """
        given an ORM instance, return a dict of
        expansion.plural_name to matching orm attribute
        """
        return {
            expansion.plural_name: getattr(orm_instance, expansion.plural_name)
            for expansion in self.expansions
        }

    def etag(self, orm_instance) -> Union[str, None]:
        """return resource etag given an orm_class instance"""
        if self.etag_attr is None:
            return None
        return getattr(orm_instance, self.etag_attr)

    def last_modified(self, orm_instance) -> Union[datetime, None]:
        """return resource last modified datetime given an orm_class instance"""
        if self.last_modified_attr is None:
            return None
        return getattr(orm_instance, self.last_modified_attr)

    def expansion_joinedloads(self):
        """
        Returns sqlalchemy joinedload() list for all possible expansions. Mostly meant for use in SupineRouter,
        to enable a single query looking up all attributes when querying by key.
        """
        # generate a single query for each specified resource expansion attribute
        # getattr(orm_class, expansion.plural_name) should return a sqlalchemy relationship()
        joined_loads = (
            joinedloads(self.orm_class, exp.plural_name) for exp in self.expansions
        )
        return list(chain.from_iterable(joined_loads))

    def _register(self):
        """
        Internal use only. Registers the plural name of this Resource so that we can use lazy evaluation to avoid
        circular reference issues
        """
        resource_key = self.plural_name
        if resource_key in _resource_registry:
            warnings.warn(f"Resource {resource_key} already registered -- overwriting")
        _resource_registry[resource_key] = self


def joinedloads(orm_class, attr_or_name):
    """
    if attr_or_name represents at least one relationship, generates joinedload() query options to load
    the relationship(s)

    calls itself recursively if the attr_or_name represents a list
    """
    attr = attr_or_name
    if isinstance(attr_or_name, str):
        attr = getattr(orm_class, attr_or_name, None)
    if isinstance(attr, InstrumentedAttribute):
        # single relationship()
        yield joinedload(attr)
    elif getattr(attr, "is_attribute", False):
        # hybrid_property with one or more relationship()s
        yield from chain.from_iterable(joinedloads(orm_class, a) for a in attr)
    else:
        warnings.warn(f"could not emit joinedload() for {orm_class}.{attr_or_name}")


def null_filter():
    """Used where a Filter is expected but no filter is necessary"""
    return None
