from unittest import mock

import pytest
from pydantic import BaseModel

from supine import Resource, SupineRouter

resource = Resource(
    singular_name="resource",
    plural_name="resources",
    orm_class=mock.Mock(),
    model=BaseModel,
    create_params=BaseModel,
    update_params=BaseModel,
)


def test_cannot_add_update_route_without_params():
    """When adding an update-route, missing update params should raise an exception"""
    router = SupineRouter()
    resource = mock.Mock(update_params=None)
    with pytest.raises(ValueError):
        router.include_update_resource(resource)


def test_cannot_add_create_route_without_params():
    """When adding a create-route, missing create params should raise an exception"""
    router = SupineRouter()
    resource = mock.Mock(create_params=None)
    with pytest.raises(ValueError):
        router.include_create_resource(resource)


def test_include_crud():
    router = SupineRouter()
    returned_functions = router.include_crud(resource)
    created_route_names = [r.name for r in router.routes]

    assert len(returned_functions) == 5
    assert created_route_names == [
        "get_resource",
        "get_resources",
        "create_resource",
        "update_resource",
        "delete_resource",
    ]
