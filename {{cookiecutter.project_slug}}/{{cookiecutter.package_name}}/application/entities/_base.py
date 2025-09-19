from sqlmodel import SQLModel

class Entity(SQLModel, table=False):
    pass
