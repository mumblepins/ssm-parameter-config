# -*- coding: utf-8 -*-
#  pylint: disable=import-outside-toplevel,no-member
from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import PARAMETER_NAME, PARAMETER_VALUE, PARAMETER_VALUE_ESCAPED

if TYPE_CHECKING:
    from ssm_parameter_config import SSMParameter


class TestSSMParameter:
    def test_create_param(self, ssm, ssm_parameter):
        sp: SSMParameter = ssm_parameter
        sp.put_parameter()
        r = ssm.get_parameter(Name=PARAMETER_NAME)
        assert r["Parameter"]["Value"] == PARAMETER_VALUE_ESCAPED

    def test_read_param_from_path(self, ssm):
        param_kwargs = {
            "Description": "Test Descrip",
            "Tags": [{"Key": "test-tag", "Value": "test-tag-value"}],
        }
        ssm.put_parameter(Name=PARAMETER_NAME, Value=PARAMETER_VALUE_ESCAPED, **param_kwargs)
        from ssm_parameter_config import SSMParameter, SSMPath

        sp_root = SSMPath(name="/test/parameter")
        sp = sp_root["config"]
        assert isinstance(sp, SSMParameter)
        assert sp.name == PARAMETER_NAME
        assert sp.value == PARAMETER_VALUE
        assert {t.key: t.value for t in sp.tags} == {"test-tag": "test-tag-value"}

    #
    #
    # def test_path(self):
    #     assert False
    #
    # def test_is_dir(self):
    #     assert False
    #
    # def test_is_file(self):
    #     assert False
