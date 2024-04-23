from typing import Iterator

import jsonlines
import pytest

from flytekit import task, workflow
from flytekit.types.iterator import JSON


def jsons():
    for index, text in enumerate(["One chinhuahua", "A german shepherd"]):
        yield {
            "file_name": f"000{index}.png",
            "text": text,
        }


def jsons_iter():
    return iter(
        [
            x
            for x in (
                {"file_name": "0000.png", "text": "One chinhuahua"},
                {"file_name": "0001.png", "text": "A german shepherd"},
            )
        ]
    )


@task
def jsons_task(x: Iterator[JSON]) -> Iterator[JSON]:
    return x


@task
def jsons_loop_task(x: Iterator[JSON]) -> Iterator[JSON]:
    for val in x:
        print(val)


@task
def jsons_iter_task(x: Iterator[JSON]) -> Iterator[JSON]:
    return x


@task
def jsonl_input(x: Iterator[JSON]):
    for val in x:
        print(val)


@task
def jsons_return_iter() -> Iterator[JSON]:
    reader = jsonlines.Reader(open("data.jsonl"))
    for obj in reader:
        yield obj


def test_jsons_tasks():
    # 1
    iterator = jsons_task(x=jsons())
    assert isinstance(iterator, Iterator)

    x, y = next(iterator), next(iterator)
    assert x == {"file_name": "0000.png", "text": "One chinhuahua"}
    assert y == {"file_name": "0001.png", "text": "A german shepherd"}

    with pytest.raises(StopIteration):
        next(iterator)

    # 2
    with pytest.raises(TypeError, match="Python value cannot be None"):
        jsons_loop_task(x=jsons())

    # 3
    iter_iterator = jsons_iter_task(x=jsons_iter())
    assert isinstance(iter_iterator, Iterator)

    # 4
    jsonl_input(x=jsonlines.Reader(open("data.jsonl")).iter())

    # 5
    return_iter_iterator = jsons_return_iter()
    assert isinstance(return_iter_iterator, Iterator)

    x, y, z = (
        next(return_iter_iterator),
        next(return_iter_iterator),
        next(return_iter_iterator),
    )
    assert x == {"file_name": "0000.png", "text": "One chinhuahua"}
    assert y == {"file_name": "0001.png", "text": "A german shepherd"}
    assert z == {
        "file_name": "0002.png",
        "text": "This is a golden retriever playing with a ball",
    }

    with pytest.raises(StopIteration):
        next(return_iter_iterator)


@workflow
def jsons_wf(x: Iterator[JSON] = jsons()) -> Iterator[JSON]:
    return jsons_task(x=x)


@workflow
def jsons_iter_wf(x: Iterator[JSON] = jsons_iter()) -> Iterator[JSON]:
    return jsons_iter_task(x=x)


def test_jsons_wf():
    # 1
    iterator = jsons_wf()
    assert isinstance(iterator, Iterator)

    x, y = next(iterator), next(iterator)
    assert x == {"file_name": "0000.png", "text": "One chinhuahua"}
    assert y == {"file_name": "0001.png", "text": "A german shepherd"}

    # 2
    iter_iterator = jsons_iter_wf()
    assert isinstance(iter_iterator, Iterator)