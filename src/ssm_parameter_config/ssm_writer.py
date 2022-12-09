# -*- coding: utf-8 -*-
# pylint: disable=too-many-arguments,too-many-locals,no-value-for-parameter
import importlib
import json
import random
import string
import sys

import click

from ssm_parameter_config import SSMConfig, SSMParameter  # nodep


@click.command()
@click.argument("input_file", type=click.Path(file_okay=True, dir_okay=False, path_type=str, allow_dash=True))
@click.argument("output", type=click.File("w"), default="-")
@click.option("--ssm-config-format", type=click.Choice(["json", "yaml"]), default="yaml")
@click.option("--output-format", type=click.Choice(["json", "shell"]), default="json")
@click.option("--as-config", is_flag=True)
@click.option("--extra-import", type=click.STRING, multiple=True)
@click.option("--extra-import-path", type=click.Path(exists=True, file_okay=False, dir_okay=True), multiple=True)
@click.option("--push-to-aws", is_flag=True)
@click.option("--parameter-name", type=click.STRING, default=None)
@click.option("--parameter-base-name", type=click.STRING, default="")
@click.option("--pretty-print-json", is_flag=True, default=True)
def cli(
    input_file: str,
    output,
    ssm_config_format,
    push_to_aws,
    output_format,
    as_config,
    extra_import,
    extra_import_path,
    parameter_name,
    parameter_base_name,
    pretty_print_json,
):
    if parameter_name is None:
        if input_file == "-":
            raise click.UsageError("Need to specify --parameter_name if reading from STDIN")
        parameter_name = input_file.split("/")[-1]
    parameter_full_name = parameter_base_name + parameter_name
    output.write(
        main(
            input_file,
            ssm_config_format,
            push_to_aws,
            output_format,
            as_config,
            extra_import,
            extra_import_path,
            parameter_full_name,
            pretty_print_json,
        )
    )


def main(
    input_file,
    ssm_config_format,
    push_to_aws,
    output_format,
    as_config,
    extra_import,
    extra_import_path,
    parameter_full_name,
    pretty_print_json,
):
    if as_config:
        for eip in extra_import_path:
            sys.path.append(str(eip))
        for ei in extra_import:
            importlib.import_module(ei)
        input_ssm_cfg = SSMConfig.from_file(input_file)
        input_ssm = input_ssm_cfg.to_parameter(
            exp_format=ssm_config_format, ssm_parameter_path=parameter_full_name, ignore_current=True
        )
    else:
        with click.open_file(input_file, "r", encoding="utf8") as fh:
            input_ssm = SSMParameter(Name=parameter_full_name, Value=fh.read())
    out = input_ssm.put_parameter(as_cli_input=not push_to_aws)
    if push_to_aws:
        return ""
    output = ""
    if output_format == "shell":
        var_name = "".join(random.choices(string.ascii_letters, k=10))  # nosec B311
        output += f"read -r -d '' {var_name} <<'EOF_{var_name}'\n"
    if pretty_print_json:
        output += json.dumps(out, indent=2)
    else:
        output += json.dumps(out)
    if output_format == "shell":
        output += f"\nEOF_{var_name}\n\n"
        output += f'aws ssm put-parameter --cli-input-json "${var_name}"\n'
    return output


if __name__ == "__main__":
    cli()
