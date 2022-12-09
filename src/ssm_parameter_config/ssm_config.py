# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
import shlex
from pathlib import Path, PurePath
from typing import Any, Dict, Iterable, Mapping, Optional, Type, Union

from pydantic import BaseSettings, ValidationError, parse_obj_as
from pydantic.env_settings import DotenvType, SettingsSourceCallable, env_file_sentinel

from ._yaml import encode_for_yaml, yaml
from .ssm_parameter import SSMParameter
from .utils import lazy_dict

StrPath = Union[str, os.PathLike, PurePath]


class LocalSSMSettings:
    __slots__ = ("local_ssm_path",)

    def __init__(self, local_ssm_path: Optional[StrPath]):
        self.local_ssm_path: Optional[StrPath] = local_ssm_path

    def __call__(self, settings: BaseSettings) -> Dict[str, Any]:
        settings_path: StrPath
        if self.local_ssm_path is not None:
            settings_path = self.local_ssm_path
        elif "LOCAL_SSM_SETTINGS_PATH" in os.environ:
            settings_path = os.environ["LOCAL_SSM_SETTINGS_PATH"]
        elif hasattr(settings.__config__, "local_ssm_settings_path"):
            settings_path = settings.__config__.local_ssm_settings_path
        else:
            return {}

        spath = Path(settings_path).expanduser()
        if not spath.exists():
            return {}

        pdict = lazy_dict(spath.read_text(encoding="utf8"))

        if settings.__config__.case_sensitive:
            return pdict

        return {k.lower(): v for k, v in pdict.items()}

    def __repr__(self) -> str:
        return f"LocalSSMSettings(yaml_file={self.local_ssm_path!r})"


class AwsSSMSettings:
    __slots__ = ("ssm_path",)

    def __init__(self, ssm_path: Optional[str]):
        self.ssm_path: Optional[str] = ssm_path

    def __call__(self, settings: BaseSettings) -> Dict[str, Any]:
        settings_path: str
        if self.ssm_path is not None:
            settings_path = self.ssm_path
        elif "AWS_SSM_SETTINGS_PATH" in os.environ:
            settings_path = os.environ["AWS_SSM_SETTINGS_PATH"]
        elif hasattr(settings.__config__, "aws_ssm_settings_path"):
            settings_path = settings.__config__.aws_ssm_settings_path
        else:
            return {}

        param = SSMParameter.get_parameter(settings_path)
        if param.value == "":
            return {}
        pdict = param.lazy_dict()
        pdict["ssm_parameter"] = param
        if settings.__config__.case_sensitive:
            return pdict

        return {k.lower(): v for k, v in pdict.items()}

    def __repr__(self) -> str:
        return f"LocalSSMSettings(yaml_file={self.ssm_path!r})"


_ssm_config_classes: list[Type[SSMConfig]] = []


class SSMConfig(BaseSettings):
    def __init__(  # pylint: disable=no-self-argument
        __pydantic_self__,
        *,
        _env_file: Optional[DotenvType] = env_file_sentinel,
        _env_file_encoding: Optional[str] = None,
        _env_nested_delimiter: Optional[str] = None,
        _secrets_dir: Optional[StrPath] = None,
        _local_ssm_path: Optional[StrPath] = None,
        _aws_ssm_path: Optional[str] = None,
        **values: Any,
    ) -> None:
        if _local_ssm_path is not None:
            values["_local_ssm_path"] = _local_ssm_path

        if _aws_ssm_path is not None:
            values["_aws_ssm_path"] = _aws_ssm_path
        super().__init__(_env_file, _env_file_encoding, _env_nested_delimiter, _secrets_dir, **values)

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
            # this is an ugly way to store these special variables without overriding
            # the whole BaseSettings._build_values function
            local_source = LocalSSMSettings(
                local_ssm_path=init_settings.init_kwargs.pop("_local_ssm_path", None)  # type: ignore[attr-defined]
            )
            aws_source = AwsSSMSettings(
                ssm_path=init_settings.init_kwargs.pop("_aws_ssm_path", None)  # type: ignore[attr-defined]
            )
            return (
                init_settings,
                local_source,
                aws_source,
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
    def from_object(cls, obj: dict[str, Any]):
        for c in reversed(_ssm_config_classes):
            try:
                new_cls = parse_obj_as(c, obj)
                break
            except ValidationError:
                pass
        else:
            raise ValueError(f"Could not parse {obj} as any of {_ssm_config_classes!r}")
        return new_cls

    @classmethod
    def from_file(cls, file: StrPath) -> SSMConfig:
        for c in reversed(_ssm_config_classes):
            try:
                new_cls = c(_local_ssm_path=file)
                break
            except ValidationError:
                pass
        else:
            raise ValueError(f"Could not parse {file!s} as any of {_ssm_config_classes!r}")
        return new_cls

    @classmethod
    def from_parameter(cls, parameter: SSMParameter) -> SSMConfig:
        ld = parameter.lazy_dict()
        new_cls = cls.from_object(ld)
        new_cls.ssm_parameter = parameter
        return new_cls

    def _write_config_env(self):
        if isinstance(self.__config__.env_file, (list, tuple)):
            efile = self.__config__.env_file[0]
        else:
            efile = self.__config__.env_file
        with open(efile, "wt", encoding="utf8") as fh:
            fh.write(self.export("env"))

    def to_parameter(self, exp_format="yaml", ssm_parameter_path: Optional[str] = None, ignore_current: bool = False):
        if ssm_parameter_path is not None:
            if not ignore_current:
                ssm_param = SSMParameter.get_parameter(ssm_parameter_path)
            else:
                ssm_param = SSMParameter(Name=ssm_parameter_path, Value="")
        else:
            ssm_param = self.ssm_parameter
        # if ssm_param.value is None or ssm_param.value == "":
        ssm_param.value = self.export(exp_format)
        if ssm_param != self.ssm_parameter:
            self.ssm_parameter = ssm_param
        return ssm_param

    def _write_config_ssm(self, exp_format, ssm_parameter_path=None, as_cli_input: bool = False):
        kwargs = {}
        if as_cli_input:
            kwargs = {"ignore_current": True}
        ssm_param = self.to_parameter(exp_format=exp_format, ssm_parameter_path=ssm_parameter_path, **kwargs)
        return ssm_param.put_parameter(as_cli_input=as_cli_input)

    def _write_config_local(self, exp_format, path):
        val = self.export(exp_format)
        with open(path, "wt", encoding="utf8") as fh:
            fh.write(val)

    def write_config(
        self,
        exp_format="yaml",
        ssm_parameter_path=None,
        local_path=None,
        as_cli_input: bool = False,
    ):
        if ssm_parameter_path is not None or (self.ssm_parameter is not None and exp_format != "env"):
            return self._write_config_ssm(exp_format, ssm_parameter_path=ssm_parameter_path, as_cli_input=as_cli_input)
        if hasattr(self.__config__, "local_settings_path") or local_path is not None:
            if local_path is not None:
                output = Path(local_path)
            else:
                output = Path(self.__config__.local_settings_path)  # type:ignore
            output = output.expanduser()
            self._write_config_local(exp_format, path=output)
        elif hasattr(self.__config__, "env_file"):
            self._write_config_env()
        else:
            raise ValueError("No SSM parameter (path) or env file defined.")
        return None
