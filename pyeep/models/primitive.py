import importlib
import logging
from typing import Any

import pydantic
from pydantic_core import core_schema
from pydantic import json_schema

log = logging.getLogger(__name__)


def get_primitive_subclass(obj: dict[str, Any]) -> type["Primitive"]:
    """Get the Primitive subclass for a serialized Primitive."""
    try:
        primitive_name = obj["primitive"]
    except Exception as e:
        raise ValueError(e)

    try:
        module_name, class_name = primitive_name.rsplit(".", 1)
    except Exception as e:
        raise ValueError(e)

    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
    except Exception as e:
        raise ValueError(
            f"invalid Primitive {module_name!r}.{class_name!r}: {e}"
        )

    if not issubclass(cls, Primitive):
        raise ValueError(
            f"{module_name}.{class_name} is not a subclass of Primitive"
        )

    return cls


class Primitive(pydantic.BaseModel):
    """Base for all serialized primitives used in pyeep."""

    primitive: str = ""

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_primitive_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("primitive", f"{cls.__module__}.{cls.__name__}")
        return data


class PrimitiveField:
    """Field annotation to serialize/deserialize a Primitive."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: pydantic.GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def validate_from_dict(
            value: dict[str, Any], info: core_schema.ValidationInfo
        ) -> Primitive:
            primitive_cls = get_primitive_subclass(value)
            return primitive_cls.model_validate(value)

        def _serialize(instance):
            return instance.model_dump()

        from_dict_schema = core_schema.chain_schema(
            [
                core_schema.dict_schema(),
                core_schema.with_info_plain_validator_function(
                    validate_from_dict
                ),
            ]
        )
        return core_schema.json_or_python_schema(
            json_schema=from_dict_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(Primitive),
                    from_dict_schema,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                _serialize
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: pydantic.GetJsonSchemaHandler,
    ) -> json_schema.JsonSchemaValue:
        # Use the same schema that would be used for `int`
        return handler(core_schema.dict_schema())


def load_primitive(obj: Any) -> Primitive:
    """Deserialize a serialized Primitive object."""
    if not isinstance(obj, dict):
        raise ValueError(f"serialized Primitive {obj!r} is not a dict")
    cls = get_primitive_subclass(obj)
    return cls.model_validate(obj)
