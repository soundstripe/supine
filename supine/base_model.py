from pydantic import BaseModel


class OrmModeBaseModel(BaseModel):
    class Config:
        orm_mode = True
