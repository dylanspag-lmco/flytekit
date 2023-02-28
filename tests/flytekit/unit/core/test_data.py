import os
import shutil
import tempfile

import fsspec
import mock
import pytest
from fsspec.implementations.arrow import ArrowFSWrapper
from pyarrow import fs

from flytekit.configuration import Config
from flytekit.core.data_persistence import FileAccessProvider, default_local_file_access_provider

local = fsspec.filesystem("file")

# def test_mlje():
#     # pyarrow stuff
#     local = fs.LocalFileSystem()
#     local_fsspec = ArrowFSWrapper(local)
#
#     s3, path = fs.FileSystem.from_uri("s3://flyte-demo/datasets/sddemo/small.parquet")
#     print(s3, path)
#     f = s3.open_input_stream(path)
#     f.readall()
#     ws3 = ArrowFSWrapper(s3)
#
#     ss3 = fs.S3FileSystem(region="us-east-2")
#
#     # base fsspec stuff
#     fs3 = fsspec.filesystem("s3")
#     fs3.cat_file("s3://flyte-demo/datasets/sddemo/small.parquet")
#
#     # Does doing this work with minio without the thing?
#     s3, path = fs.FileSystem.from_uri(
#         "s3://my-s3-bucket/metadata/flytesnacks/development/am9s9q2dfrkrfnc7x9nd/user_inputs"
#     )
#     # If you don't have http, it will try to use SSL.
#     # TODO: check the sandbox configuration to see what it uses.
#     local_s3 = fs.S3FileSystem(
#         access_key="minio", secret_key="miniostorage", endpoint_override="http://localhost:30002"
#     )
#     wr_s3 = ArrowFSWrapper(local_s3)


@mock.patch("google.auth.compute_engine._metadata")  # to prevent network calls
@mock.patch("flytekit.core.data_persistence.UUID")
def test_path_getting(mock_uuid_class, mock_gcs):
    mock_uuid_class.return_value.hex = "abcdef123"

    # Testing with raw output prefix pointing to a local path
    local_raw_fp = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix="/tmp/unittestdata")
    assert local_raw_fp.get_random_remote_path() == "/tmp/unittestdata/abcdef123"
    assert local_raw_fp.get_random_remote_path("/fsa/blah.csv") == "/tmp/unittestdata/abcdef123/blah.csv"
    assert local_raw_fp.get_random_remote_directory() == "/tmp/unittestdata/abcdef123"

    # Test local path and directory
    assert local_raw_fp.get_random_local_path() == "/tmp/unittest/local_flytekit/abcdef123"
    assert local_raw_fp.get_random_local_path("xjiosa/blah.txt") == "/tmp/unittest/local_flytekit/abcdef123/blah.txt"
    assert local_raw_fp.get_random_local_directory() == "/tmp/unittest/local_flytekit/abcdef123"

    # Test with remote pointed to s3.
    s3_fa = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix="s3://my-s3-bucket")
    assert s3_fa.get_random_remote_path() == "s3://my-s3-bucket/abcdef123"
    assert s3_fa.get_random_remote_directory() == "s3://my-s3-bucket/abcdef123"
    # trailing slash should make no difference
    s3_fa = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix="s3://my-s3-bucket/")
    assert s3_fa.get_random_remote_path() == "s3://my-s3-bucket/abcdef123"
    assert s3_fa.get_random_remote_directory() == "s3://my-s3-bucket/abcdef123"

    # Testing with raw output prefix pointing to file://
    file_raw_fp = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix="file:///tmp/unittestdata")
    assert file_raw_fp.get_random_remote_path() == "/tmp/unittestdata/abcdef123"
    assert file_raw_fp.get_random_remote_path("/fsa/blah.csv") == "/tmp/unittestdata/abcdef123/blah.csv"
    assert file_raw_fp.get_random_remote_directory() == "/tmp/unittestdata/abcdef123"

    g_fa = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix="gs://my-s3-bucket/")
    assert g_fa.get_random_remote_path() == "gs://my-s3-bucket/abcdef123"


@mock.patch("flytekit.core.data_persistence.UUID")
def test_default_file_access_instance(mock_uuid_class):
    mock_uuid_class.return_value.hex = "abcdef123"

    assert default_local_file_access_provider.get_random_local_path().endswith("/sandbox/local_flytekit/abcdef123")
    assert default_local_file_access_provider.get_random_local_path("bob.txt").endswith("abcdef123/bob.txt")

    assert default_local_file_access_provider.get_random_local_directory().endswith("sandbox/local_flytekit/abcdef123")

    x = default_local_file_access_provider.get_random_remote_path()
    assert x.endswith("raw/abcdef123")
    x = default_local_file_access_provider.get_random_remote_path("eve.txt")
    assert x.endswith("raw/abcdef123/eve.txt")
    x = default_local_file_access_provider.get_random_remote_directory()
    assert x.endswith("raw/abcdef123")


@pytest.fixture
def source_folder():
    # Set up source directory for testing
    parent_temp = tempfile.mkdtemp()
    src_dir = os.path.join(parent_temp, "source")
    nested_dir = os.path.join(src_dir, "nested")
    local.mkdir(nested_dir)
    local.touch(os.path.join(src_dir, "original.txt"))
    local.touch(os.path.join(nested_dir, "more.txt"))
    yield src_dir
    shutil.rmtree(parent_temp)


# Add some assertions
def test_local_raw_fsspec(source_folder):
    with tempfile.TemporaryDirectory() as dest_tmpdir:
        local.put(source_folder, dest_tmpdir, recursive=True)

    new_temp_dir_2 = tempfile.mkdtemp()
    new_temp_dir_2 = os.path.join(new_temp_dir_2, "doesnotexist")
    local.put(source_folder, new_temp_dir_2, recursive=True)


# Add some assertions
def test_local_provider(source_folder):
    dc = Config.for_sandbox().data_config
    with tempfile.TemporaryDirectory() as dest_tmpdir:
        provider = FileAccessProvider(local_sandbox_dir="/tmp/unittest", raw_output_prefix=dest_tmpdir, data_config=dc)
        doesnotexist = provider.get_random_remote_directory()
        provider.put_data(source_folder, doesnotexist, is_multipart=True)

        exists = provider.get_random_remote_directory()
        provider._default_remote.mkdir(exists)
        provider.put_data(source_folder, exists, is_multipart=True)


@pytest.mark.needs_local_sandbox
def test_s3_provider(source_folder):
    # Running mkdir on s3 filesystem doesn't do anything so leaving out for now
    dc = Config.for_sandbox().data_config
    provider = FileAccessProvider(
        local_sandbox_dir="/tmp/unittest", raw_output_prefix="s3://my-s3-bucket/testdata/", data_config=dc
    )
    doesnotexist = provider.get_random_remote_directory()
    provider.put_data(source_folder, doesnotexist, is_multipart=True)
