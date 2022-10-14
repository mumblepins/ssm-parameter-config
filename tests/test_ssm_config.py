# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, List

from ssm_parameter_config import SSMConfig

if TYPE_CHECKING:
    pass


class Config(SSMConfig):
    athena_database: str
    athena_workgroup: str
    email_from: str
    email_to: List[str]
    email_subject: str

    class Config:
        local_settings_path = "ssm_config.yaml"


class TestSSMConfig:
    def test_get_from_config(self, config_yaml, monkeypatch):
        monkeypatch.chdir(config_yaml)
        cfg = Config()
        assert cfg.email_subject == "New records"
