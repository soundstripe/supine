import hashlib
import warnings
from datetime import datetime
from enum import Enum
from itertools import chain
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

import fastapi.routing
from fastapi import Body, Depends, HTTPException, params, Query
from fastapi.datastructures import Default
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, joinedload, Session
from starlette import routing
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute
from starlette.status import HTTP_304_NOT_MODIFIED, HTTP_404_NOT_FOUND
from starlette.types import ASGIApp

from supine.api_response import ApiResponse, ApiResponseStatus
from supine.filter import DataclassFilterMixin
from supine.pagination import Pagination
from supine.resource import Resource

RFC9110_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


class SupineRouter(fastapi.routing.APIRouter):
    def __init__(
        self,
        *,
        prefix: str = "",
        tags: Optional[List[Union[str, Enum]]] = None,
        dependencies: Optional[Sequence[params.Depends]] = None,
        default_response_class: Type[Response] = Default(JSONResponse),
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        callbacks: Optional[List[BaseRoute]] = None,
        routes: Optional[List[routing.BaseRoute]] = None,
        redirect_slashes: bool = True,
        default: Optional[ASGIApp] = None,
        dependency_overrides_provider: Optional[Any] = None,
        route_class: Type[APIRoute] = APIRoute,
        on_startup: Optional[Sequence[Callable[[], Any]]] = None,
        on_shutdown: Optional[Sequence[Callable[[], Any]]] = None,
        deprecated: Optional[bool] = None,
        include_in_schema: bool = True,
        generate_unique_id_function: Callable[[APIRoute], str] = Default(
            generate_unique_id
        ),
        sqlalchemy_sessionmaker=None,
    ) -> None:
        self.sqlalchemy_sessionmaker = sqlalchemy_sessionmaker
        super().__init__(
            prefix=prefix,
            tags=tags,
            dependencies=dependencies,
            default_response_class=default_response_class,
            responses=responses,
            callbacks=callbacks,
            routes=routes,
            redirect_slashes=redirect_slashes,
            default=default,
            dependency_overrides_provider=dependency_overrides_provider,
            route_class=route_class,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            generate_unique_id_function=generate_unique_id_function,
        )

    def session(self):
        """
        fastapi.Depends()-compatible function to provide a sqlalchemy session
        which rolls back on error
        """
        session = self.sqlalchemy_sessionmaker()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def set_cache_headers(
        request: Request,
        response: Response,
        max_age=0,
        etag=None,
        last_modified: datetime = None,
    ):
        if last_modified:
            last_modified = last_modified.strftime(RFC9110_DATE_FORMAT)

        if etag and request.headers.get("if-none-match", None) == etag:
            raise HTTPException(HTTP_304_NOT_MODIFIED)
        if last_modified and request.headers.get("if-modified-since", None):
            raise HTTPException(HTTP_304_NOT_MODIFIED)

        response.headers[
            "cache-control"
        ] = f"private, must-revalidate, max-age={max_age}"
        if etag:
            response.headers["etag"] = etag
        if last_modified:
            response.headers["last-modified"] = last_modified

    def include_get_resource_by_id(self, resource: Resource):
        @self.get(
            f"/{resource.singular_name}/{{key}}",
            response_model=resource.result,
            response_model_exclude_unset=True,
            name=f"get_{resource.singular_name}",
            tags=[resource.plural_name],
        )
        def get_obj(
            request: Request,
            response: Response,
            obj: resource.orm_class = Depends(self.make_resource_getter(resource)),
            expand: bool = Query(
                False,
                description="If true, related objects will be returned along with the primary result.",
            ),
        ):
            results = {resource.singular_name: obj}
            if expand:
                results.update(resource._get_expansion_dict(obj))

            etag = resource.etag(obj)
            last_modified = resource.last_modified(obj)
            max_age = resource.max_age
            self.set_cache_headers(
                request,
                response,
                max_age=max_age,
                etag=etag,
                last_modified=last_modified,
            )

            return resource.result(status=ApiResponseStatus.success, result=results)

        return get_obj

    def include_get_resource_list(self, resource: Resource):
        @self.get(
            f"/{resource.singular_name}",
            response_model=resource.list_result,
            response_model_exclude_unset=True,
            name=f"get_{resource.plural_name}",
            tags=[resource.plural_name],
        )
        def get_objects(
            pagination: Pagination = Depends(),
            query_filter: DataclassFilterMixin = Depends(resource.query_filter),
            session: Session = Depends(self.session),
        ):
            query = select(resource.orm_class)
            if query_filter is not None:
                query = query_filter.modify_query(query)
            results = pagination.fetch_paginated(session, query)
            if query_filter is not None:
                results = query_filter.modify_results(results)

            return resource.list_result(
                status=ApiResponseStatus.success,
                result={resource.plural_name: results},
                pagination=pagination,
            )

        return get_objects

    def include_create_resource(self, resource):
        if resource.create_params is None:
            raise ValueError(
                f"must set {resource!r}.create_params to include this route"
            )

        @self.post(
            f"/{resource.singular_name}",
            response_model=resource.result,
            response_model_exclude_unset=True,
            name=f"create_{resource.singular_name}",
            tags=[resource.plural_name],
        )
        def create_object(
            create_params: resource.create_params = Body(),
            session: Session = Depends(self.session),
        ):
            obj = resource.orm_class(**create_params.dict())
            session.add(obj)
            session.commit()
            return resource.result(
                status=ApiResponseStatus.success,
                result={resource.singular_name: obj},
            )

        return create_object

    def include_update_resource(self, resource):
        if resource.update_params is None:
            raise ValueError(
                f"must set {resource!r}.update_params to include this route"
            )

        @self.patch(
            f"/{resource.singular_name}/{{key}}",
            response_model=resource.result,
            response_model_exclude_unset=True,
            name=f"update_{resource.singular_name}",
            tags=[resource.plural_name],
        )
        def update_object(
            obj: resource.orm_class = Depends(self.make_resource_getter(resource)),
            update_params: resource.update_params = Body(),
            session: Session = Depends(self.session),
        ):
            for attr_name, val in update_params.dict(exclude_unset=True).items():
                setattr(obj, attr_name, val)
            session.commit()
            return resource.result(
                status=ApiResponseStatus.success,
                result={resource.singular_name: obj},
            )

    def include_delete_resource(self, resource):
        @self.delete(
            f"/{resource.singular_name}/{{key}}",
            response_model=ApiResponse,
            response_model_exclude_unset=True,
            name=f"delete_{resource.singular_name}",
            tags=[resource.plural_name],
        )
        def delete_object(key: int, session: Session = Depends(self.session)):
            obj = session.get(resource.orm_class, key)
            if obj is None:
                raise HTTPException(
                    HTTP_404_NOT_FOUND, f"specified {resource.singular_name} not found"
                )

            session.delete(obj)
            session.commit()
            return ApiResponse(status=ApiResponseStatus.success)

    def make_resource_getter(self, resource: Resource):
        """
        Returns a Depends() compatible function for getting a single SQLAlchemy instance by
        its primary key. Uses SQLAlchemy's session.get().

        First-level relationship()s on the SQLAlchemy classes will be loaded with a join automatically
        if the expand parameter is set on the request.

        Raises FastAPI 404 exception if object does not exist in the database
        """

        def inner(
            key: int,
            expand: bool = Query(False),
            session: Session = Depends(self.session),
        ):
            expansion_loader_options = []
            if expand:
                # generate a single query for each specified resource expansion attribute
                # getattr(orm_class, expansion.plural_name) should return a sqlalchemy relationship()
                expansion_loader_options = list(
                    chain.from_iterable(
                        generate_joinedloads(resource.orm_class, exp.plural_name)
                        for exp in resource.runtime_expansions
                    )
                )
            obj = session.get(resource.orm_class, key, options=expansion_loader_options)
            if obj is None:
                raise HTTPException(
                    HTTP_404_NOT_FOUND, f"specified {resource.singular_name} not found"
                )
            return obj

        return inner


def generate_joinedloads(orm_class, attr_or_name):
    attr = attr_or_name
    if isinstance(attr_or_name, str):
        attr = getattr(orm_class, attr_or_name, None)
    if isinstance(attr, InstrumentedAttribute):
        # single relationship()
        yield joinedload(attr)
    elif getattr(attr, "is_attribute", False):
        # hybrid_property with one or more relationship()s
        yield from chain.from_iterable(generate_joinedloads(orm_class, a) for a in attr)
    else:
        warnings.warn(f"could not emit joinedload() for {orm_class}.{attr_or_name}")
