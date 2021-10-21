"""Test local execution of files that use functools to decorate tasks and workflows."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

test_module_dir = Path(os.path.dirname(__file__))


def test_wrapped_tasks_happy_path(capfd):
    subprocess.run(
        [sys.executable, str(test_module_dir / "simple_decorator.py")],
        env={"SCRIPT_INPUT": "10"},
        text=True,
    )
    out = capfd.readouterr().out

    assert out.strip().split("\n") == [
        "before running my_task",
        "try running my_task",
        "running my_task",
        "finally after running my_task",
        "after running my_task",
        "11",
    ]


def test_wrapped_tasks_error(capfd):
    subprocess.run(
        [sys.executable, str(test_module_dir / "simple_decorator.py")],
        env={"SCRIPT_INPUT": "0"},
        text=True,
    )
    out = capfd.readouterr().out

    assert out.strip().split("\n") == [
        "before running my_task",
        "try running my_task",
        "error running my_task: my_task failed with input: 0",
        "finally after running my_task",
        "after running my_task",
    ]


def test_stacked_wrapped_tasks(capfd):
    subprocess.run(
        [sys.executable, str(test_module_dir / "stacked_decorators.py")],
        env={"SCRIPT_INPUT": "10"},
        text=True,
    )
    out = capfd.readouterr().out
    assert out.strip().split("\n") == [
        "running task_decorator_1",
        "running task_decorator_2",
        "running task_decorator_3",
        "running my_task",
        "11",
    ]


def test_unwrapped_task():
    p = subprocess.Popen(
        [sys.executable, str(test_module_dir / "unwrapped_decorator.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, error = p.communicate()
    error_str = error.decode().strip().split("\n")[-1]
    assert error_str == (
        "ValueError: Type <class 'inspect._empty'> not supported currently in Flytekit. "
        "Please register a new transformer"
    )


def test_nested_function():
    p = subprocess.Popen(
        [sys.executable, str(test_module_dir / "nested_function.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, error = p.communicate()
    error_str = error.decode().strip().split("\n")[-1]
    assert error_str.startswith(
        "ValueError: TaskFunction cannot be a nested/inner or local function."
    )
