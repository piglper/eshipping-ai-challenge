"""Command line: ``python -m eshipping_ai.synthetic [--spec PATH] [--out DIR]``."""

import argparse
from pathlib import Path

from eshipping_ai.synthetic.build import build
from eshipping_ai.synthetic.spec import load_spec


def main(argv: list[str] | None = None) -> None:
    """Generate the synthetic data set."""
    parser = argparse.ArgumentParser(description="Generate the synthetic data set.")
    parser.add_argument("--spec", type=Path, default=Path("data_sample/spec/sample.yaml"))
    parser.add_argument("--out", type=Path, default=Path("data_sample/build"))
    args = parser.parse_args(argv)
    result = build(load_spec(args.spec), args.out)
    print(
        f"{len(result.mail_files)} correos, {result.erp_file.name} y {result.gold_file.name} "
        f"en {args.out}"
    )


if __name__ == "__main__":
    main()
