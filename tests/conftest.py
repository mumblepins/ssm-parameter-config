# -*- coding: utf-8 -*-
#  pylint: disable=wrong-import-position,import-outside-toplevel
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Generator

import boto3
import pytest
from moto import mock_ssm

if TYPE_CHECKING:
    from ssm_parameter_config import SSMParameter

from ssm_parameter_config.utils import ssm_curly_to_special

PARAMETER_NAME = "/test/parameter/config"
PARAMETER_VALUE = "test_value {{brackets}}\n😀"
PARAMETER_VALUE_ESCAPED = ssm_curly_to_special(PARAMETER_VALUE)


@pytest.fixture(scope="module")
def config_yaml(tmp_path_factory):
    file_data = """athena_database: test_db
athena_workgroup: test_wg
email_from: no-reply@test.com
email_to:
  - test@test.com
email_subject: New records"""
    tmp_dir = tmp_path_factory.mktemp("config_path")
    cfg_file = tmp_dir / "ssm_config.yaml"
    cfg_file.write_text(file_data)
    return tmp_dir


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-2"


@pytest.fixture(scope="function")
def ssm(aws_credentials):
    with mock_ssm():
        yield boto3.client("ssm")


@pytest.fixture(scope="function")
def ssm_parameter(ssm) -> Generator[SSMParameter, None, None]:
    from ssm_parameter_config import SSMParameter

    sp = SSMParameter(Name=PARAMETER_NAME, Value=PARAMETER_VALUE)

    yield sp
