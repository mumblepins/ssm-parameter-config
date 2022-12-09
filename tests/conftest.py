# -*- coding: utf-8 -*-
#  pylint: disable=wrong-import-position,import-outside-toplevel
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, List

import boto3
import pytest
from moto import mock_ssm

from ssm_parameter_config import SSMConfig, SSMParameter
from ssm_parameter_config.utils import ssm_curly_to_special


@pytest.fixture(scope="module")
def config_yaml(tmp_path_factory) -> Path:
    # language=yaml
    tmp_dir = tmp_path_factory.mktemp("config_path")
    cfg_file = tmp_dir / "ssm_config.yaml"
    cfg_file.write_text(INPUT)
    return cfg_file


@pytest.fixture(scope="function")
def ssm_config(config_yaml):
    cfg = TConfig(_local_ssm_path=config_yaml)
    return cfg


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
    sp = SSMParameter(Name=PARAMETER_NAME, Value=PARAMETER_VALUE)

    yield sp


@pytest.fixture(scope="function")
def ssm_config_in_store(ssm_config, ssm):
    cfg_param = ssm_config.to_parameter(ssm_parameter_path="/basic/non/existent/path")
    cfg_param.put_parameter()
    return cfg_param


PARAMETER_NAME = "/test/parameter/config"
PARAMETER_VALUE = "test_value {{brackets}}\n😀"
PARAMETER_VALUE_ESCAPED = ssm_curly_to_special(PARAMETER_VALUE)
INPUT = """athena_database: test_db
athena_workgroup: test_wg
email_from: no-reply@test.com
email_to:
  - test@test.com
email_subject: New records
email_text: |
  test_value_with_brackets
  {{brackets}}"""
EXPECTED_DICT = {
    "ssm_parameter": None,
    "athena_database": "test_db",
    "athena_workgroup": "test_wg",
    "email_from": "no-reply@test.com",
    "email_to": ["test@test.com"],
    "email_subject": "New records",
    "email_text": "test_value_with_brackets\n{{brackets}}",
}
EXPECTED_ESCAPED_PARAM = """athena_database: test_db
athena_workgroup: test_wg
email_from: no-reply@test.com
email_to:
  - test@test.com
email_subject: New records
email_text: |-
  test_value_with_brackets
  ʃbracketsʅ
"""


class TConfig(SSMConfig):
    athena_database: str
    athena_workgroup: str
    email_from: str
    email_to: List[str]
    email_subject: str
    email_text: str

    class Config:
        local_ssm_settings_path = "ssm_config.yaml"
