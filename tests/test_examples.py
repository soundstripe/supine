import pytest

from examples import customer_api
from httpx import HTTPStatusError
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def app():
    return customer_api.app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_get_customer(client):
    response = client.get("/customer/1")
    assert response.json() == {
        "status": "success",
        "result": {
            "customer": {
                "customer_id": 1,
                "first_name": "Sherlock",
                "last_name": "Holmes",
                "territory_id": 1,
            }
        },
    }


def test_get_customer_not_found(client):
    response = client.get("/customer/2")
    with pytest.raises(HTTPStatusError, match="404"):
        response.raise_for_status()
    assert response.json() == {
        "status": "error",
        "detail": "specified customer not found",
    }


def test_get_customer_expanded(client):
    response = client.get("/customer/1", params=dict(expand=1))
    assert response.json() == {
        "status": "success",
        "result": {
            "customer": {
                "customer_id": 1,
                "first_name": "Sherlock",
                "last_name": "Holmes",
                "territory_id": 1,
            },
            "territories": [{"territory_id": 1, "name": "London"}],
        },
    }


def test_get_customers(client):
    response = client.get("/customer")
    assert response.json() == {
        "status": "success",
        "result": {
            "customers": [
                {
                    "customer_id": 1,
                    "first_name": "Sherlock",
                    "last_name": "Holmes",
                    "territory_id": 1,
                }
            ]
        },
        "pagination": {"start": 0, "count": 1, "total": 1},
    }


def test_create_customer(client):
    response = client.post(
        "/customer",
        json={
            "first_name": "James",
            "last_name": "Watson",
            "territory_id": 1,
        },
    )
    assert response.json() == {
        "status": "success",
        "result": {
            "customer": {
                "customer_id": 2,
                "first_name": "James",
                "last_name": "Watson",
                "territory_id": 1,
            }
        },
    }


def test_delete_customer(client):
    response = client.delete("/customer/2")
    assert response.json() == {"status": "success"}


def test_update_customer(client):
    response = client.patch("/customer/1", json={"last_name": "Cumberbatch"})
    assert response.json() == {
        "status": "success",
        "result": {
            "customer": {
                "customer_id": 1,
                "first_name": "Sherlock",
                "last_name": "Cumberbatch",
                "territory_id": 1,
            }
        },
    }


def test_get_territory(client):
    response = client.get("/territory/1")
    assert response.json() == {
        "status": "success",
        "result": {"territory": {"territory_id": 1, "name": "London"}},
    }


def test_get_territories(client):
    response = client.get("/territory")
    assert response.json() == {
        "status": "success",
        "result": {"territories": [{"territory_id": 1, "name": "London"}]},
        "pagination": {"start": 0, "count": 1, "total": 1},
    }
