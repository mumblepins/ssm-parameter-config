# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from io import StringIO

import dotenv
from ruamel.yaml import YAMLError

from ._yaml import yaml

SSM_PARAMETER_SUBSTITUTION = (
    ("{{", "ʃ"),  # U+0283	ʃ	ca 83	LATIN SMALL LETTER ESH
    ("}}", "ʅ"),  # U+0285	ʅ	ca 85	LATIN SMALL LETTER SQUAT REVERSED ESH
)


def ssm_curly_to_special(val):
    for sub_set in SSM_PARAMETER_SUBSTITUTION:
        val = val.replace(*sub_set)
    return val


def ssm_special_to_curly(val):
    for sub_set in SSM_PARAMETER_SUBSTITUTION:
        val = val.replace(sub_set[1], sub_set[0])
    return val


def lazy_dict(value):
    """First try as json, then try as yaml, and then try as env file"""
    try:
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        pass
    try:
        return yaml.load(value)
    except YAMLError:
        pass
    return dict(dotenv.dotenv_values(stream=StringIO(value)))
