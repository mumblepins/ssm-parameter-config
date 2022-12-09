# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from ruamel.yaml import YAML

from ssm_parameter_config import SSMParameter
from ssm_parameter_config.ssm_parameter import SSMDataType, SSMTier, SSMType
from tests.conftest import EXPECTED_DICT, EXPECTED_ESCAPED_PARAM, TConfig

yaml = YAML(typ="safe")

PARAM_STRING = """{
  "name": "/basic/non/existent/path",
  "description": null,
  "value": "athena_database: test_db\\nathena_workgroup: test_wg\\nemail_from: no-reply@test.com\\nemail_to:\\n  - test@test.com\\nemail_subject: New records\\nemail_text: |-\\n  test_value_with_brackets\\n  {{brackets}}\\n",
  "type": "String",
  "key_id": null,
  "allowed_pattern": null,
  "version": null,
  "last_modified_date": null,
  "tier": "Standard",
  "data_type": "text",
  "tags": []
}"""  # noqa: B950


class TestSSMConfig:
    def test_get_from_local_file(self, config_yaml):
        ssm_config = TConfig(_local_ssm_path=config_yaml)
        assert ssm_config.dict() == EXPECTED_DICT

    def test_get_from_local_file_config(self, config_yaml, monkeypatch):
        monkeypatch.chdir(config_yaml.parent)
        ssm_config = TConfig()
        assert ssm_config.dict() == EXPECTED_DICT

    def test_get_from_local_file_env(self, config_yaml, monkeypatch):
        monkeypatch.setenv("LOCAL_SSM_SETTINGS_PATH", str(config_yaml.resolve()))
        ssm_config = TConfig()
        assert ssm_config.dict() == EXPECTED_DICT

    def test_get_from_aws_path(self, ssm_config_in_store):
        cfg = TConfig(_aws_ssm_path=ssm_config_in_store.name)
        exp_dict = EXPECTED_DICT.copy()
        exp_dict.pop("ssm_parameter")
        cfg_dict = cfg.dict()
        cfg_dict.pop("ssm_parameter")
        assert cfg_dict == exp_dict

    def test_to_parameter(self, ssm, ssm_config):
        cfg_param = ssm_config.to_parameter(ssm_parameter_path="/basic/non/existent/path")
        assert isinstance(cfg_param, SSMParameter)
        assert cfg_param.json(indent=2) == PARAM_STRING
        cfg_param.put_parameter()
        assert ssm.get_parameter(Name=cfg_param.name)["Parameter"]["Value"] == EXPECTED_ESCAPED_PARAM

    def test_export_yaml(self, ssm_config):
        output = ssm_config.export(exp_format="yaml", ssm_format=False)
        assert "{{brackets}}" in output
        output = ssm_config.export(exp_format="yaml", ssm_format=True)
        assert "{{brackets}}" not in output
        assert yaml.load(output)["email_from"] == "no-reply@test.com"
        output = ssm_config.export(exp_format="json")
        assert json.loads(output)["email_from"] == "no-reply@test.com"

    def test_write_config(self, ssm, ssm_config):
        out = ssm_config.write_config(ssm_parameter_path="/no/path/here", as_cli_input=True)

        assert out == {
            "Name": "/no/path/here",
            "Type": SSMType.string,
            "Tier": SSMTier.standard,
            "DataType": SSMDataType.text,
            "Value": EXPECTED_ESCAPED_PARAM,
            "Overwrite": True,
        }
