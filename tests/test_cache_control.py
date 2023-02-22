from datetime import datetime
from unittest import mock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from supine.base_model import OrmModeBaseModel
from supine.resource import Resource
from supine.router import SupineRouter

MISSING = object()


class R(OrmModeBaseModel):
    data: str


@pytest.fixture()
def app():
    return FastAPI()


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def session():
    return mock.Mock()


@pytest.fixture()
def supine_router(session):
    return SupineRouter(default_session_factory=lambda: session)


@pytest.fixture()
def resource():
    return Resource(
        singular_name="resource",
        plural_name="resources",
        orm_class=mock.Mock(),
        model=R,
    )


@pytest.mark.parametrize(
    "last_modified_date,expected",
    [
        (datetime(2020, 1, 1, 0, 0, 0), "Wed, 01 Jan 2020 00:00:00 GMT"),
        (None, MISSING),
    ],
    ids=["last_modified_available", "last_modified_missing"],
)
def test_last_modified(
    app, client, session, resource, supine_router, last_modified_date, expected
):
    """Ensures a get-by-id route return last-modified header when the resource has it available"""
    resource.last_modified_attr = "last_modified"

    supine_router.include_get_resource_by_id(resource)
    app.include_router(supine_router)

    mock_obj = mock.Mock(data="test data", last_modified=last_modified_date)
    session.get.return_value = mock_obj

    response = client.get("/resource/1")
    assert response.headers.get("last-modified", MISSING) == expected


def test_if_modified_since(app, client, session, resource, supine_router):
    """Ensures a 304 Not Modified response is sent when the request headers match the found record"""
    resource.last_modified_attr = "last_modified"

    supine_router.include_get_resource_by_id(resource)
    app.include_router(supine_router)

    mock_obj = mock.Mock(data="test data", last_modified=datetime(2020, 1, 1, 0, 0, 0))
    session.get.return_value = mock_obj

    response = client.get(
        "/resource/1", headers={"if-modified-since": "Wed, 01 Jan 2020 00:00:00 GMT"}
    )
    assert response.status_code == 304


@pytest.mark.parametrize(
    "etag,expected",
    [
        ("uniqueVersionId123", "uniqueVersionId123"),
        (None, MISSING),
    ],
    ids=["etag_available", "etag_missing"],
)
def test_etag(app, client, session, resource, supine_router, etag, expected):
    """Ensures a get-by-id route return etag header when the resource has it available"""
    resource.etag_attr = "etag"

    supine_router.include_get_resource_by_id(resource)
    app.include_router(supine_router)

    mock_obj = mock.Mock(data="test data", etag=etag)
    session.get.return_value = mock_obj

    response = client.get("/resource/1")
    assert response.headers.get("etag", MISSING) == expected


def test_if_none_match(app, client, session, resource, supine_router):
    """Ensures a 304 Not Modified response is sent when the request headers match the found record"""
    resource.etag_attr = "etag"

    supine_router.include_get_resource_by_id(resource)
    app.include_router(supine_router)

    mock_obj = mock.Mock(data="test data", etag="uniqueVersionId123")
    session.get.return_value = mock_obj

    response = client.get(
        "/resource/1", headers={"if-none-match": "uniqueVersionId123"}
    )
    assert response.status_code == 304


def test_max_age(app, client, session, resource, supine_router):
    """Ensures cache-control header has max-age set as specified when requesting object by id"""
    resource.max_age = 120

    supine_router.include_get_resource_by_id(resource)
    app.include_router(supine_router)

    mock_obj = mock.Mock(data="test data")
    session.get.return_value = mock_obj

    response = client.get("/resource/1")
    assert "max-age=120" in response.headers["cache-control"]
