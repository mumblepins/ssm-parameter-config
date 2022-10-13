# -*- coding: utf-8 -*-
from typing import Mapping

from pydantic.json import pydantic_encoder
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

yaml = YAML()
yaml.default_flow_style = False
yaml.width = 120  # type: ignore
yaml.sequence_dash_offset = 2


def encode_for_yaml(obj):
    if isinstance(obj, Mapping):
        return {k: encode_for_yaml(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [encode_for_yaml(v) for v in obj]
    try:
        obj = pydantic_encoder(obj)
    except TypeError:
        pass
    if isinstance(obj, str) and "\n" in obj:
        return LiteralScalarString(obj)
    return obj
