
# Supine

Opinionated FastAPI/SQLAlchemy helpers for lazy coders who just want to REST.

Exposing table after table via a REST API becomes a tedious chore very quickly. FastAPI and other lightweight frameworks make the tasks simple, but setting up a new project still requires many decisions. Supine aims to reduce the decision-making time by offering opinionated helpers that provide sane, extensible defaults.


## Features

- Quick CRUD routes for database Resources
- Quick filtering for lists of Resources
- Standardized JSON response structure
- Standardized update/PATCH requests
- Pagination for list results
- Automatic cache headers (that won't break anything)
- Remains compatible with FastAPI features and conventions
- Prevent mistakes by making it easier to write correct code


## Installation

Install Supine with pypi

```bash
  pip install supine
```

## Example

In Supine, you define Resources which usually correlate to your database tables.

Pardon the slightly long example, but Supine is not meant for "toy" projects. You will still need to define your orm model, de/serialization model, models for create/update parameters, and a model for filtering lists of your Resources.

```python
import sqlalchemy.orm
import fastapi

from supine import SupineRouter, OrmModeBaseModel, Resource

# Setup app and SQLAlchemy engine as usual
app = fastapi.FastAPI()
engine = sqlalchemy.create_engine()
S = sqlalchemy.orm.sessionmaker(bind=engine)
OrmBase = sqlalchemy.orm.declarative_base()


# Normal SQLAlchemy ORM Model
class CustomerOrm(OrmBase):
    __tablename__ = 'customer'

    customer_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    first_name = sqlalchemy.Column(sqlalchemy.String(256))
    last_name = sqlalchemy.Column(sqlalchemy.String(256))

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


# Normal Pydantic De/Serialization Model
class Customer(OrmModeBaseModel):
    """A basic customer. Belongs to one territory."""
    customer_id: int  # these attribute names correspond to the orm model attributes
    first_name: str
    last_name: str
    full_name: str


# Sample Data
with S.begin() as session:
    OrmBase.metadata.create_all(bind=session.get_bind())
    session.add_all([
        CustomerOrm(first_name='Sherlock', last_name='Holmes'),
        CustomerOrm(first_name='John', last_name='Watson'),
    ])

# Supine Resource (dataclass) to tie everything together
customer_resource = Resource(
    singular_name='customer',
    plural_name='customers',
    orm_class=CustomerOrm,
    model=Customer,
)

# SupineRouter is a standard FastAPI APIRouter with some helpers
supine_router = SupineRouter(sqlalchemy_sessionmaker=S)

# Register `/customer/{key}` to get a single customer
# The `get_customer` variable is simply to improve your code's search-ability
get_customer = supine_router.include_get_resource_by_id(customer_resource)

# Register `/customer` to get a list of all customers
get_customers = supine_router.include_get_resource_list(customer_resource)

# SupineRouter is a normal FastAPI router, you can add normal routes
# This example also uses the Resource.list_result helper and the SupineRouter.session helper
@supine_router.get('/top_customer', response_model=customer_resource.list_result)
def get_top_customers(
    session: sqlalchemy.orm.Session = fastapi.Depends(supine_router.session)
):
    top_customers = session.scalars(sqlalchemy.select(CustomerOrm)).fetchall()
    return {'result': {'customers': top_customers}}

# Don't forget to include your SupineRouter in your app
app.include_router(supine_router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)

```


## Assumptions and Opinions

Assumptions:

* you want to use [FastAPI](https://github.com/tiangolo/fastapi)
* you want to use [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)
* you favor extensibility, code completion, and searchable code over single-line-of-code magic

Opinions:

* REST APIs should respond with JSON
* JSON responses should be able to contain some response metadata
  * this allows use of even rudimentary http client interfaces
* Response Model, Creation Parameters, and Update Parameters should be three separate models
  * they rarely match enough to share code (required params, defaults, calculated fields)
  * they may however share validation types/documentation which makes Pydantic a great fit
  * your work should concentrate on your models, and any orm complexity should be hidden
  * adding a field to the model should add it to the response immediately
* Start/Count pagination is good enough for most people
* Requiring more requests is better than requiring more API complexity
* Responses should be cacheable whenever possible


## Authors

- [@soundstripe](https://www.github.com/soundstripe) Steven James

