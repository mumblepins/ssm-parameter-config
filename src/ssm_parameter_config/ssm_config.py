# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
import shlex
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Type

from pydantic import BaseSettings, ValidationError, parse_obj_as
from pydantic.env_settings import SettingsSourceCallable

from ._yaml import encode_for_yaml, yaml
from .ssm_parameter import SSMParameter
from .utils import lazy_dict


def local_ssm_settings_source(settings: BaseSettings) -> dict[str, Any]:
    if "LOCAL_SSM_SETTINGS_PATH" in os.environ:
        settings_path = Path(os.environ["LOCAL_SSM_SETTINGS_PATH"])
    elif hasattr(settings.__config__, "local_settings_path"):
        settings_path = Path(settings.__config__.local_settings_path)  # type:ignore
    else:
        return {}

    ssm_path = settings_path.expanduser()
    pdict = lazy_dict(ssm_path.read_text(encoding="utf8"))

    if settings.__config__.case_sensitive:
        return pdict

    return {k.lower(): v for k, v in pdict.items()}


def aws_ssm_settings_source(settings: BaseSettings) -> dict[str, Any]:
    if "AWS_SSM_SETTINGS_PATH" not in os.environ:
        return {}
    param = SSMParameter.get_parameter(os.environ["AWS_SSM_SETTINGS_PATH"])
    pdict = param.lazy_dict()
    pdict["ssm_parameter"] = param
    if settings.__config__.case_sensitive:
        return pdict

    return {k.lower(): v for k, v in pdict.items()}


_ssm_config_classes: list[Type[SSMConfig]] = []


class SSMConfig(BaseSettings):
    ssm_parameter: Optional[SSMParameter] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _ssm_config_classes.append(cls)

    class Config:
        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ):
            return (
                init_settings,
                local_ssm_settings_source,
                aws_ssm_settings_source,
                env_settings,
                file_secret_settings,
            )

    def export(self, exp_format="yaml", exclude_ssm=True, ssm_format=False, **dump_kwargs):
        dict_args = {"exclude_none": True, "by_alias": True, "exclude_defaults": True}
        if exclude_ssm:
            dict_args["exclude"] = {"ssm_parameter"}
        if exp_format == "json":
            kwargs = {"separators": (",", ":")}
            kwargs.update(dump_kwargs)
            output = self.json(**kwargs, **dict_args)
        elif exp_format == "yaml":
            kwargs = {}
            kwargs.update(dump_kwargs)
            out = io.StringIO()
            yaml.dump(encode_for_yaml(self.dict(**dict_args)), out, **kwargs)
            output = out.getvalue()
        elif exp_format == "env":
            exp = []
            for k, v in self.dict(**dict_args).items():
                if isinstance(v, (Mapping, Iterable)) and not isinstance(v, (str, bytes, bytearray)):
                    v = self.__config__.json_dumps(v, default=self.__json_encoder__)
                v = shlex.quote(v)
                exp.append(f"{k.upper()}={v}")
            exp.append("")
            output = "\n".join(exp)
        else:
            raise ValueError(f"Format {exp_format} not supported.")
        if ssm_format:
            return SSMParameter.get_parameter_value(output)
        return output

    @classmethod
    def from_parameter(cls, parameter: SSMParameter) -> SSMConfig:
        ld = parameter.lazy_dict()
        for c in reversed(_ssm_config_classes):
            try:
                new_cls = parse_obj_as(c, ld)
                break
            except ValidationError:
                pass
        else:
            raise ValueError(f"Could not parse {ld} as any of {_ssm_config_classes}")
        new_cls.ssm_parameter = parameter
        return new_cls

    def _write_config_env(self):
        if isinstance(self.__config__.env_file, (list, tuple)):
            efile = self.__config__.env_file[0]
        else:
            efile = self.__config__.env_file
        with open(efile, "wt", encoding="utf8") as fh:
            fh.write(self.export("env"))

    def _write_config_ssm(self, exp_format, ssm_parameter_path=None):
        val = self.export(exp_format)
        if ssm_parameter_path is not None:
            ssm_param = SSMParameter.get_parameter(ssm_parameter_path)
        else:
            ssm_param = self.ssm_parameter
        ssm_param.put_parameter(val)

    def _write_config_local(self, exp_format, path):
        val = self.export(exp_format)
        with open(path, "wt", encoding="utf8") as fh:
            fh.write(val)

    def write_config(self, exp_format="yaml", ssm_parameter_path=None, local_path=None):
        if ssm_parameter_path is not None or (self.ssm_parameter is not None and exp_format != "env"):
            self._write_config_ssm(exp_format, ssm_parameter_path=ssm_parameter_path)
        elif hasattr(self.__config__, "local_settings_path") or local_path is not None:
            if local_path is not None:
                output = Path(local_path)
            else:
                output = Path(self.__config__.local_settings_path)
            output = output.expanduser()
            self._write_config_local(exp_format, path=output)
        elif hasattr(self.__config__, "env_file"):
            self._write_config_env()
        else:
            raise ValueError("No SSM parameter (path) or env file defined.")
