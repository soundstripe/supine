import dataclasses

import sqlalchemy.orm
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import StaticPool
from sqlalchemy.orm import Mapper
from starlette.exceptions import HTTPException

from supine.base_model import OrmModeBaseModel
from supine.exception_handler import supine_http_exception_handler
from supine.filter import DataclassFilterMixin, Filter
from supine.resource import Resource

from supine.router import SupineRouter

engine = sqlalchemy.create_engine(
    "sqlite://?check_same_thread=False", poolclass=StaticPool, echo=True
)
S = sqlalchemy.orm.sessionmaker(bind=engine)
OrmBase = sqlalchemy.orm.declarative_base()


class TerritoryOrm(OrmBase):
    __tablename__ = "territory"
    territory_id: Mapper[int] = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name: Mapper[str] = sqlalchemy.Column(sqlalchemy.String(256))


class CustomerOrm(OrmBase):
    __tablename__ = "customer"

    customer_id: Mapper[int] = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    first_name: Mapper[str] = sqlalchemy.Column(sqlalchemy.String(256))
    last_name: Mapper[str] = sqlalchemy.Column(sqlalchemy.String(256))
    territory_id: Mapper[int] = sqlalchemy.Column(
        sqlalchemy.ForeignKey("territory.territory_id")
    )

    territory = sqlalchemy.orm.relationship(TerritoryOrm)
    territories = sqlalchemy.orm.relationship(
        TerritoryOrm, uselist=True, overlaps="territory"
    )


class Customer(OrmModeBaseModel):
    """A basic customer. Belongs to one territory"""

    customer_id: int
    first_name: str
    last_name: str
    territory_id: int


class CustomerCreateParams(BaseModel):
    first_name: str
    last_name: str
    territory_id: int


class CustomerUpdateParams(BaseModel):
    first_name: str = None
    last_name: str = None
    territory_id: int = None


class Territory(OrmModeBaseModel):
    """A basic territory"""

    territory_id: int
    name: str


@dataclasses.dataclass
class CustomerFilter(DataclassFilterMixin, Filter):
    first_name: str = None
    territory_id: int = None


# Sample Data
with S.begin() as session:
    OrmBase.metadata.create_all(bind=session.get_bind())
    session.add(TerritoryOrm(territory_id=1, name="London"))
    session.add(
        CustomerOrm(
            customer_id=1, first_name="Sherlock", last_name="Holmes", territory_id=1
        )
    )

customer_resource = Resource(
    singular_name="customer",
    plural_name="customers",
    orm_class=CustomerOrm,
    model=Customer,
    create_params=CustomerCreateParams,
    update_params=CustomerUpdateParams,
    query_filter=CustomerFilter,
    expansions=["territories"],
)
territory_resource = Resource(
    singular_name="territory",
    plural_name="territories",
    orm_class=TerritoryOrm,
    model=Territory,
)

app = FastAPI(swagger_ui_parameters={"displayOperationId": True})
app.add_exception_handler(HTTPException, supine_http_exception_handler)

supine_router = SupineRouter(sqlalchemy_sessionmaker=S)
get_customer = supine_router.include_get_resource_by_id(customer_resource)
get_customers = supine_router.include_get_resource_list(customer_resource)
create_customer = supine_router.include_create_resource(customer_resource)
update_customer = supine_router.include_update_resource(customer_resource)
delete_customer = supine_router.include_delete_resource(customer_resource)
# even shorter shorthand for the above 5 lines:
# get_customer, get_customers, create_customer, update_customer, delete_customer = (
#   supine_router.include_crud(customer_resource)
# )
get_territory = supine_router.include_get_resource_by_id(territory_resource)
get_territories = supine_router.include_get_resource_list(territory_resource)

app.include_router(supine_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
