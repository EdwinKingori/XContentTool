from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """
    Root base for all request schemas (Create, Update).

    Does NOT set from_attributes — these schemas are built from raw request
    data (JSON body, query params), never from ORM objects.
    """
    pass


class BaseResponse(AppBaseModel):
    """
    Base for all response / Read schemas.

    from_attributes=True tells Pydantic to read field values from object
    attributes instead of dict keys, which is required when constructing
    a schema directly from a SQLAlchemy ORM instance:

        TenantRead.model_validate(tenant_orm_object)
    """
    model_config = ConfigDict(from_attributes=True)
