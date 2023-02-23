import warnings
from datetime import datetime
from enum import Enum
from itertools import chain
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

from fastapi import Body, Depends, HTTPException, params, Query
from fastapi.datastructures import Default
from fastapi.routing import APIRoute, APIRouter
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, joinedload, Session
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


def supine_generate_unique_id(route: APIRoute):
    """
    Simplify operation IDs so that generated API clients have simpler function names.

    If you are using a Resource your operation ids will be based on the singular name:
      Example: singular_name='product'
          get_product
          get_products
          create_product
          update_product
          delete_product

    Note this function does no name scoping, and so is prone to collisions.
    Be careful with your Resource naming.
    """
    return f"{route.name}"


class SupineRouter(APIRouter):
    def __init__(
        self,
        *,
        prefix: str = "",
        tags: Optional[List[Union[str, Enum]]] = None,
        dependencies: Optional[Sequence[params.Depends]] = None,
        default_response_class: Type[Response] = Default(JSONResponse),
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        callbacks: Optional[List[BaseRoute]] = None,
        routes: Optional[List[BaseRoute]] = None,
        redirect_slashes: bool = True,
        default: Optional[ASGIApp] = None,
        dependency_overrides_provider: Optional[Any] = None,
        route_class: Type[APIRoute] = APIRoute,
        on_startup: Optional[Sequence[Callable[[], Any]]] = None,
        on_shutdown: Optional[Sequence[Callable[[], Any]]] = None,
        deprecated: Optional[bool] = None,
        include_in_schema: bool = True,
        generate_unique_id_function: Callable[
            [APIRoute], str
        ] = supine_generate_unique_id,
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
            orm_instance: resource.orm_class = Depends(
                self.orm_instance_getter_factory(resource)
            ),
            expand: bool = Query(
                False,
                description="If true, related objects will be returned along with the primary result.",
            ),
        ):
            results = {resource.singular_name: orm_instance}
            if expand:
                results.update(resource.get_expansion_dict(orm_instance))

            self.set_cache_headers(
                request,
                response,
                max_age=resource.max_age,
                etag=resource.etag(orm_instance),
                last_modified=resource.last_modified(orm_instance),
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
            orm_instances = pagination.fetch_paginated(session, query)
            if query_filter is not None:
                orm_instances = query_filter.modify_results(orm_instances)

            return resource.list_result(
                status=ApiResponseStatus.success,
                result={resource.plural_name: orm_instances},
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
            orm_instance = resource.orm_class(**create_params.dict())
            session.add(orm_instance)
            session.commit()
            return resource.result(
                status=ApiResponseStatus.success,
                result={resource.singular_name: orm_instance},
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
            orm_instance: resource.orm_class = Depends(
                self.orm_instance_getter_factory(resource)
            ),
            update_params: resource.update_params = Body(),
            session: Session = Depends(self.session),
        ):
            for attr_name, val in update_params.dict(exclude_unset=True).items():
                setattr(orm_instance, attr_name, val)
            session.commit()
            return resource.result(
                status=ApiResponseStatus.success,
                result={resource.singular_name: orm_instance},
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
            orm_instance = session.get(resource.orm_class, key)
            if orm_instance is None:
                raise HTTPException(
                    HTTP_404_NOT_FOUND, f"specified {resource.singular_name} not found"
                )

            session.delete(orm_instance)
            session.commit()
            return ApiResponse(status=ApiResponseStatus.success)

    def orm_instance_getter_factory(self, resource: Resource):
        """
        Returns a Depends()-compatible function for getting a single SQLAlchemy instance by
        its primary key. Uses the session created by .sqlalchemy_sessionmaker, fetches the instance
        by using SQLAlchemy's session.get().

        First-level relationship()s on the SQLAlchemy classes will be loaded with a join automatically
        if the expand parameter is set on the request.

        Raises FastAPI 404 exception if object does not exist in the database
        """

        def inner(
            key: int,
            expand: bool = Query(False),
            session: Session = Depends(self.session),
        ):
            query_options = []
            if expand:
                query_options = resource.expansion_joinedloads()

            obj = session.get(resource.orm_class, key, options=query_options)
            if obj is None:
                raise HTTPException(
                    HTTP_404_NOT_FOUND, f"specified {resource.singular_name} not found"
                )
            return obj

        return inner
