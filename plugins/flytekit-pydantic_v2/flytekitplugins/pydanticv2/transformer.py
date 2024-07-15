from pydantic import BaseModel
from typing import Dict, Type, Any
from flytekit import FlyteContext
from flytekit.types.file import FlyteFile, FlyteFilePathTransformer
from flytekit.core.context_manager import FlyteContextManager
from flytekit.core.type_engine import TypeEngine, TypeTransformer
from flytekit.models import literals, types
from flytekit.models.types import LiteralType
from flytekit.models.literals import Literal, Scalar, Schema
from google.protobuf import struct_pb2 as _struct
from google.protobuf import json_format as _json_format
from pydantic import BaseModel, model_serializer


@model_serializer
def ser_flyte_file(self) -> Dict[str, Any]:
    lv = FlyteFilePathTransformer().to_literal(FlyteContextManager.current_context(), self, FlyteFile, None)
    return {"path": lv.scalar.blob.uri, "testing_pydantic_flyetfile": "testing_pydantic_flyetfile"}

setattr(FlyteFile, "ser_flyte_file", ser_flyte_file)

class PydanticTransformer(TypeTransformer[BaseModel]):
    def __init__(self):
        super().__init__("Pydantic Transformer", BaseModel)

    def get_literal_type(self, t: Type[BaseModel]) -> LiteralType:
        return types.LiteralType(simple=types.SimpleType.STRUCT)

    def to_literal(self,
                   ctx: FlyteContext,
                   python_val: BaseModel,
                   python_type: Type[BaseModel],
                   expected: types.LiteralType, ) -> Literal:
        json_str = python_val.model_dump_json()
        return Literal(scalar=Scalar(generic=_json_format.Parse(json_str, _struct.Struct())))  # type: ignore

    def to_python_value(self, ctx: FlyteContext, lv: Literal, expected_python_type: Type[BaseModel]) -> BaseModel:
        json_str = _json_format.MessageToJson(lv.scalar.generic)
        return expected_python_type.model_validate_json(json_str)


TypeEngine.register(PydanticTransformer())