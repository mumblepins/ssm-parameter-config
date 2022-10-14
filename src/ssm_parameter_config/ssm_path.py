# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import PurePath, _PosixFlavour  # type:ignore
from urllib.parse import quote_from_bytes as urlquote_from_bytes

import boto3


class _SSMFlavour(_PosixFlavour):
    is_supported = bool(boto3)

    def parse_parts(self, parts):
        drv, root, parsed = super().parse_parts(parts)
        for part in parsed[1:]:
            if part == "..":
                index = parsed.index(part)
                parsed.pop(index - 1)
                parsed.remove(part)
        return drv, root, parsed

    def make_uri(self, path):
        # We represent the path using the local filesystem encoding,
        # for portability to other applications.
        bpath = bytes(path)
        return "ssm:/" + urlquote_from_bytes(bpath)


_ssm_flavour = _SSMFlavour()


class PureSSMPath(PurePath):
    @classmethod
    def _from_parts(cls, args, *_args, **_kwargs):
        """
        SSM has no concept of a relative path, but root paths don't need the forward slash
        """
        if len(args) > 0:
            if not args[0].startswith("/"):
                args = ["/"] + list(args)
        else:
            args = ["/"]
        return super()._from_parts(args, *_args, **_kwargs)

    _flavour = _ssm_flavour

    @classmethod
    def from_uri(cls, uri):
        if not uri.startswith("ssm://"):
            raise ValueError("Provided uri doesn't seem to be an SSM URI!")
        return cls(uri[5:])
