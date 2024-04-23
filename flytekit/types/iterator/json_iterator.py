from typing import Iterator, Type, TypeAlias

import jsonlines

from flytekit import FlyteContext, Literal, LiteralType
from flytekit.core.type_engine import (
    TypeEngine,
    TypeTransformer,
    TypeTransformerFailedError,
)
from flytekit.models.core import types as _core_types
from flytekit.models.literals import Blob, BlobMetadata, Scalar
from flytekit.types.file import FlyteFile


class JSONIterator:
    def __init__(self, reader: jsonlines.Reader):
        self._reader = reader
        self._reader_iter = reader.iter()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._reader_iter)
        except StopIteration:
            self._reader.close()
            raise StopIteration("File handler is exhausted")


class JSON:
    JSONType: TypeAlias = dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None

    @classmethod
    def upload_to_jsonl(cls, python_val: Iterator[JSONType]) -> str:
        remote_path = FlyteFile.new_remote_file()

        with remote_path.open("w") as fp:
            with jsonlines.Writer(fp) as writer:
                for json_val in python_val:
                    writer.write(json_val)

        return remote_path.path

    @classmethod
    def iterator(cls, ctx: FlyteContext, uri: str) -> JSONIterator:
        fs = ctx.file_access.get_filesystem_for_path(uri)

        fp = fs.open(uri, "r")
        reader = jsonlines.Reader(fp)

        return JSONIterator(reader)


class JSONIteratorTransformer(TypeTransformer[Iterator[JSON]]):
    JSON_ITERATOR_FORMAT = "JSONL"

    def __init__(self):
        super().__init__("JSON Iterator", Iterator[JSON])

    def get_literal_type(self, t: Type[JSON]) -> LiteralType:
        return LiteralType(
            blob=_core_types.BlobType(
                format=self.JSON_ITERATOR_FORMAT,
                dimensionality=_core_types.BlobType.BlobDimensionality.SINGLE,
            )
        )

    def to_literal(
        self,
        ctx: FlyteContext,
        python_val: Iterator[JSON],
        python_type: Type[JSON],
        expected: LiteralType,
    ) -> Literal:
        remote_path = JSON.upload_to_jsonl(python_val)

        meta = BlobMetadata(
            type=_core_types.BlobType(
                format=self.JSON_ITERATOR_FORMAT,
                dimensionality=_core_types.BlobType.BlobDimensionality.SINGLE,
            )
        )
        return Literal(scalar=Scalar(blob=Blob(metadata=meta, uri=remote_path)))

    def to_python_value(self, ctx: FlyteContext, lv: Literal, expected_python_type: Type[JSON]) -> JSONIterator:
        try:
            uri = lv.scalar.blob.uri
        except AttributeError:
            raise TypeTransformerFailedError(f"Cannot convert from {lv} to {expected_python_type}")

        return JSON.iterator(ctx, uri)

    def guess_python_type(self, literal_type: LiteralType) -> Type[JSON]:
        if (
            literal_type.blob is not None
            and literal_type.blob.dimensionality == _core_types.BlobType.BlobDimensionality.SINGLE
            and literal_type.blob.format == self.JSON_ITERATOR_FORMAT
        ):
            return JSON

        raise ValueError(f"Transformer {self} cannot reverse {literal_type}")


TypeEngine.register(JSONIteratorTransformer())