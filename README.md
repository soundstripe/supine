
# Supine

Opinionated FastAPI/SQLAlchemy helpers for lazy coders who just want to REST.

Exposing table after table via a REST API becomes a tedious chore very quickly. FastAPI and other lightweight frameworks make the tasks simple, but setting up a new project still requires many decisions. Supine aims to reduce the decision-making time by offering opinionated helpers that provide sane, extensible defaults.


## Features

- Quick route setup
- Filter framework
- Standardized JSON response structure
- Standardized update/PATCH requests
- Pagination for list results
- Automatic cache headers (that won't break anything)
- Remains compatible with FastAPI features and conventions


## Installation

Install Supine with pypi

```bash
  pip install supine
```

## Example

In Supine, you define Resources which usually correlate to your database tables.

Pardon the slightly long example, but Supine is not meant for "toy" projects. You will still need to define your orm model, de/serialization model, models for create/update parameters, and a model for filtering lists of your Resources.

```python
from supine import SupineRouter

# Setup app and SQLAlchemy engine as usual
app = FastAPI()
engine = sqlalchemy.create_engine()
S = sessionmaker(bind=engine)
OrmBase = sqlalchemy.orm.declarative_base()
session_factory = make_session_factory()

# SQLAlchemy ORM Model
class CustomerOrm(OrmBase):
    __tablename__ = 'customer'

    customer_id: Mapper[int] = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    first_name: Mapper[str] = sqlalchemy.Column(sqlalchemy.String(256))
    last_name: Mapper[str] = sqlalchemy.Column(sqlalchemy.String(256))


# Pydantic De/Serialization Model 
class Customer(OrmModeBaseModel):
    """A basic customer. Belongs to one territory"""
    customer_id: int
    first_name: str
    last_name: str


# Supine Resource (dataclass) to tie everything together
customer_resource = Resource(
    singular_name='customer',
    plural_name='customers',
    orm_class=CustomerOrm,
    model=Customer,
)

# Sample Data
with S.begin() as session:
    OrmBase.metadata.create_all(bind=session.get_bind())
    session.add_all([
        CustomerOrm(first_name='Sherlock', last_name='Holmes'),
        CustomerOrm(first_name='John', last_name='Watson'),
    ])

# SupineRouter is a standard FastAPI APIRouter with some helpers
supine_router = SupineRouter(default_session_factory=session_factory)

# Register `/customer/{key}` to get a single customer
# The `get_customer` variable is simply to improve your code's searchability
get_customer = supine_router.include_get_resource_by_id(customer_resource)

# Register `/customer` to get a list of all customers
get_customers = supine_router.include_get_resource_list(customer_resource)

app.include_router(supine_router)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)

```


## Authors

- [@soundstripe](https://www.github.com/soundstripe) Steven James

