"""
Base models and utilities for MongoDB ObjectId handling
"""

from typing import Any, Annotated
from pydantic import BaseModel, Field, GetJsonSchemaHandler, ConfigDict
from pydantic_core import core_schema
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )
    
    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str):
            if ObjectId.is_valid(value):
                return ObjectId(value)
        raise ValueError("Invalid ObjectId")
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, field_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        return {
            "type": "string",
            "examples": ["507f1f77bcf86cd799439011"],
        }


# Type alias for convenience
ObjectIdStr = Annotated[str, Field(..., description="MongoDB ObjectId as string")]


class MongoBaseModel(BaseModel):
    """Base model for MongoDB documents with ObjectId handling"""
    
    model_config = ConfigDict(
        # Allow population by field name (for MongoDB's _id field)
        populate_by_name=True,
        # Use enum values instead of names
        use_enum_values=True,
        # JSON encoders for special types
        json_encoders={
            ObjectId: str
        },
        # Allow arbitrary types
        arbitrary_types_allowed=True
    )
