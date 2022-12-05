# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from ruamel.yaml import YAML

from ssm_parameter_config import SSMParameter

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
    def test_get_from_config(self, ssm_config):
        assert ssm_config.email_subject == "New records"

    def test_to_parameter(self, ssm, ssm_config):
        cfg_param = ssm_config.to_parameter(ssm_parameter_path="/basic/non/existent/path")
        assert isinstance(cfg_param, SSMParameter)
        assert cfg_param.json(indent=2) == PARAM_STRING

    # def test_to_ssm(self,config_yaml,monkeypatch,ssm):

    def test_export_yaml(self, ssm_config):
        output = ssm_config.export(exp_format="yaml", ssm_format=False)
        assert "{{brackets}}" in output
        output = ssm_config.export(exp_format="yaml", ssm_format=True)
        assert "{{brackets}}" not in output
        assert yaml.load(output)["email_from"] == "no-reply@test.com"
        output = ssm_config.export(exp_format="json")
        assert json.loads(output)["email_from"] == "no-reply@test.com"
