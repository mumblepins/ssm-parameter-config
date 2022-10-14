# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterator, Optional

import boto3
from botocore.client import BaseClient
from pydantic import BaseModel, PrivateAttr, parse_obj_as
from pydantic.utils import to_camel
from signed_pickle import DumperSigner

from .ssm_path import PureSSMPath
from .utils import lazy_dict, ssm_curly_to_special, ssm_special_to_curly

if TYPE_CHECKING:
    from .ssm_config import SSMConfig

# since SSM Parameters can't have {{ }} in them, we substitute these values

logger = logging.getLogger()


class Tag(BaseModel):
    key: str
    value: str

    class Config:
        alias_generator = to_camel


class SSMType(str, Enum):
    string = "String"
    string_list = "StringList"
    secure_string = "SecureString"


class SSMTier(str, Enum):
    standard = "Standard"
    advanced = "Advanced"
    intelligent_tiering = "Intelligent-Tiering"


class SSMDataType(str, Enum):
    text = "text"
    ec2_image = "aws:ec2:image"
    ssm_integration = "aws:ssm:integration"


class SSMPath(BaseModel):
    """kind of like a pathlib path, but not quite"""

    name: str
    _listed: bool = PrivateAttr(False)
    _children: dict[str, SSMPath] = PrivateAttr({})
    _aws_client_kwargs: dict[str, Any] = PrivateAttr(default={})

    def __getitem__(self, item):
        if isinstance(item, tuple):
            this = self
            for i in item:
                this = this[i]
            return this
        try:
            return getattr(self, item)
        except AttributeError:
            pass
        self._fetch_children()
        if item in self._children:
            return self._children[item]
        nc = SSMPath(name=str(self.path / item))
        self._children[item] = nc
        return nc

    def __setitem__(self, item, value):
        if isinstance(item, tuple):
            this = self
            for i in item[:-1]:
                this = this[i]
            this[item[-1]] = value
            return
        try:
            setattr(self, item, value)
            return
        except ValueError:
            pass
        self._children[item] = value

    @property
    def path(self):
        return PureSSMPath(self.name)

    def fetch_parameters(self, path):
        ssm = self.ssm_client
        get_params_pager = ssm.get_paginator("get_parameters_by_path")
        desc_params_pager = ssm.get_paginator("describe_parameters")
        params = {}

        # fetch descriptions
        for page in desc_params_pager.paginate(
            ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [path]}]
        ):
            for p in page["Parameters"]:
                params[p["Name"]] = p
        # fetch values
        for page in get_params_pager.paginate(Path=path, Recursive=True):
            for p in page["Parameters"]:
                params[p["Name"]].update(p)

        for p in params.values():
            p["Value"] = ssm_special_to_curly(p["Value"])
            param = parse_obj_as(SSMParameter, p)

            rel_path = param.path.relative_to(self.path).parts
            self[rel_path] = param
            parts = []
            for part in rel_path[:-1]:
                parts.append(part)
                self[tuple(parts)]._listed = True  # pylint:disable=protected-access
        self._listed = True

    def _fetch_children(self):
        if self._listed:
            return

        self._listed = True
        ssm = self.ssm_client
        logger.info("Getting children for %s", self.name)
        get_params_pager = ssm.get_paginator("get_parameters_by_path")
        desc_params_pager = ssm.get_paginator("describe_parameters")
        params = {}

        # fetch descriptions
        for page in desc_params_pager.paginate(
            ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [self.name]}]
        ):
            for p in page["Parameters"]:
                params[p["Name"]] = p
        # fetch values
        for page in get_params_pager.paginate(Path=self.name, Recursive=True):
            for p in page["Parameters"]:
                params[p["Name"]].update(p)

        for p in params.values():
            p["Value"] = ssm_special_to_curly(p["Value"])
            param = parse_obj_as(SSMParameter, p)
            rel_path = param.path.relative_to(self.path).parts
            self[rel_path] = param
            parts = []
            for part in rel_path[:-1]:
                parts.append(part)
                self[tuple(parts)]._listed = True  # pylint:disable=protected-access

    def iterdir(self) -> Iterator[SSMPath]:
        self._fetch_children()

        yield from self._children.values()

    def is_dir(self):
        return True

    def is_file(self):
        return not self.is_dir()

    def set_aws_client_kwargs(self, **kwargs):
        self._aws_client_kwargs = kwargs

    @property
    def ssm_client(self):
        return boto3.client("ssm", **self._aws_client_kwargs)


class SSMParameter(SSMPath):
    # name (from SSMPATH) # from get_param..
    description: Optional[str] = None  # from describe_param
    value: Optional[str] = None  # from get_param..
    type: SSMType = SSMType.string  # from get_param..
    key_id: Optional[str] = None  # from describe_param
    allowed_pattern: Optional[str] = None  # from describe_param
    version: Optional[int] = None  # from get_param..
    last_modified_date: Optional[datetime] = None  # from get_param..
    tier: SSMTier = SSMTier.standard  # from describe_param
    data_type: SSMDataType = SSMDataType.text  # from get_param..
    tags: list[Tag] = []  # from list_tags
    _decoded_value: Any = PrivateAttr(default=None)
    _got_tags: bool = PrivateAttr(default=False)

    class Config:
        alias_generator = to_camel
        exclude_none = True

    def __getattribute__(self, item):
        # if item == "value" and super().__getattribute__("value") is None:
        #     # lazily fetch value upon first read
        #     self._fetch_value()
        if item == "tags" and not super().__getattribute__("_got_tags"):
            self._fetch_tags()
        return super().__getattribute__(item)

    def is_dir(self):
        return False

    def as_ssm_config(self) -> SSMConfig:
        from .ssm_config import SSMConfig  # pylint:disable=import-outside-toplevel

        return SSMConfig.from_parameter(self)

    # def _fetch_value(self):
    #     ssm: BaseClient = self.ssm_client
    #     try:
    #         param = ssm.get_parameter(Name=self.name)["Parameter"]
    #     except (IndexError, ssm.exceptions.ParameterNotFound):
    #         self.__setattr__("value", "")
    #         return
    #     new_param = parse_obj_as(SSMParameter, param)
    #     new_vals = new_param.dict(exclude_unset=True, exclude_none=True, exclude_defaults=True)
    #     # new_vals['value'] = new_vals['value'].
    #     for k, v in new_vals.items():
    #         self.__setattr__(k, v)

    def _fetch_tags(self):
        ssm: BaseClient = self.ssm_client
        try:
            tags = ssm.list_tags_for_resource(ResourceType="Parameter", ResourceId=self.name)
            self.tags = parse_obj_as(list[Tag], tags["TagList"])
            self._got_tags = True
        except ssm.exceptions.ParameterNotFound:
            pass

    @property
    def decoded_value(self):
        if self._decoded_value is None:
            try:
                decoded_val = base64.b64decode(self.value.strip(), validate=True)
                self._decoded_value = DumperSigner.load(decoded_val)[0].decode("utf8")
            except ValueError:
                self._decoded_value = self.value
        return self._decoded_value

    def lazy_dict(self):
        return lazy_dict(self.decoded_value)

    @classmethod
    def get_parameter(cls, name: str, default_value: str = ""):
        ssm = boto3.client("ssm")
        try:
            param = ssm.get_parameter(Name=name)["Parameter"]
            param.update(ssm.describe_parameters(ParameterFilters=[{"Key": "Name", "Values": [name]}])["Parameters"][0])
            tags = ssm.list_tags_for_resource(ResourceType="Parameter", ResourceId=name)
            param["Tags"] = tags["TagList"]
            param["Value"] = ssm_special_to_curly(param["Value"])
            return parse_obj_as(cls, param)
        except (IndexError, ssm.exceptions.ParameterNotFound):
            pass
        return cls(Name=name, Value=default_value)

    @staticmethod
    def get_parameter_value(val):
        if len(val) > 4096:
            val = base64.b64encode(DumperSigner().dump(val.encode("utf8"))).decode("utf8")

        return ssm_curly_to_special(val)

    def put_parameter(self, new_value=None):
        val = self.get_parameter_value(new_value or self.value)
        ssm = boto3.client("ssm")
        kwargs = self.dict(
            exclude_none=True,
            # exclude_defaults=True,
            by_alias=True,
            exclude={"version", "last_modified_date", "value", "tags"},
            # include={"type"},
        )

        kwargs["Value"] = val
        kwargs["Overwrite"] = True
        ssm.put_parameter(**kwargs)
