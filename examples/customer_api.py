import dataclasses

import sqlalchemy.orm
import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
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


# ORM MODELS ##################################################################


class TerritoryOrm(OrmBase):
    __tablename__ = "territory"
    territory_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String(256))


class CustomerOrm(OrmBase):
    __tablename__ = "customer"

    customer_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    first_name = sqlalchemy.Column(sqlalchemy.String(256))
    last_name = sqlalchemy.Column(sqlalchemy.String(256))
    territory_id = sqlalchemy.Column(sqlalchemy.ForeignKey("territory.territory_id"))

    territory = sqlalchemy.orm.relationship(TerritoryOrm)
    territories = sqlalchemy.orm.relationship(
        TerritoryOrm, uselist=True, overlaps="territory"
    )


# RESPONSE AND PARAM MODELS ###################################################


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


# FILTER MODELS ###############################################################


@dataclasses.dataclass
class CustomerFilter(DataclassFilterMixin, Filter):
    # this class enables query params first_name and territory_id to be used to
    # filter REST calls getting a list of customers
    # The Mixin automatically filters the generated SQLAlchemy query, but you can
    # override the filter_query() function to provide custom SQL tweaking
    first_name: str = Query(None, description="customer's first name", max_length=255)
    territory_id: int = Query(None, description="customer's territory id", ge=1)


# SAMPLE DATA #################################################################

with S.begin() as session:
    OrmBase.metadata.create_all(bind=session.get_bind())
    session.add(TerritoryOrm(territory_id=1, name="London"))
    session.add(
        CustomerOrm(
            customer_id=1, first_name="Sherlock", last_name="Holmes", territory_id=1
        )
    )

# RESOURCES ###################################################################

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

# API AND ROUTES ##############################################################

app = FastAPI(swagger_ui_parameters={"displayOperationId": True})
app.add_exception_handler(HTTPException, supine_http_exception_handler)

supine_router = SupineRouter(sqlalchemy_sessionmaker=S)

# the variable names here are just a convention, making it easy to find these routes later
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
