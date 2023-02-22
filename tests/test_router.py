from unittest import mock

import pytest

from supine import SupineRouter


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
