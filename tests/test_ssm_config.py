# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import List

from ruamel.yaml import YAML

from ssm_parameter_config import SSMConfig, SSMParameter


class Config(SSMConfig):
    athena_database: str
    athena_workgroup: str
    email_from: str
    email_to: List[str]
    email_subject: str
    email_text: str

    class Config:
        local_settings_path = "ssm_config.yaml"


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
    def test_get_from_config(self, config_yaml, monkeypatch):
        monkeypatch.chdir(config_yaml)
        cfg = Config()
        assert cfg.email_subject == "New records"

    def test_to_parameter(self, config_yaml, monkeypatch):
        monkeypatch.chdir(config_yaml)
        cfg = Config()
        cfg_param = cfg.to_parameter(ssm_parameter_path="/basic/non/existent/path")
        assert isinstance(cfg_param, SSMParameter)
        assert cfg_param.json(indent=2) == PARAM_STRING

    def test_export_yaml(self, config_yaml, monkeypatch):
        monkeypatch.chdir(config_yaml)
        cfg = Config()
        output = cfg.export(exp_format="yaml", ssm_format=False)
        assert "{{brackets}}" in output
        output = cfg.export(exp_format="yaml", ssm_format=True)
        assert "{{brackets}}" not in output
        assert yaml.load(output)["email_from"] == "no-reply@test.com"
        output = cfg.export(exp_format="json")
        assert json.loads(output)["email_from"] == "no-reply@test.com"
