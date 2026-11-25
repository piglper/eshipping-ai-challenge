"""Command line: ``python -m eshipping_ai.synthetic [--spec PATH] [--out DIR] [--copies N]``."""

import argparse
from pathlib import Path

from eshipping_ai.synthetic.build import build
from eshipping_ai.synthetic.scale import replicate
from eshipping_ai.synthetic.spec import load_spec


def main(argv: list[str] | None = None) -> None:
    """Generate the synthetic data set."""
    parser = argparse.ArgumentParser(description="Generate the synthetic data set.")
    parser.add_argument("--spec", type=Path, default=Path("data_sample/spec/sample.yaml"))
    parser.add_argument("--out", type=Path, default=Path("data_sample/build"))
    parser.add_argument(
        "--copies", type=int, default=1, help="renumbered copies of every shipment (F4.5)"
    )
    args = parser.parse_args(argv)
    spec = load_spec(args.spec)
    result = build(replicate(spec, args.copies) if args.copies > 1 else spec, args.out)
    print(
        f"{len(result.mail_files)} correos, {result.erp_file.name} y {result.gold_file.name} "
        f"en {args.out}"
    )


if __name__ == "__main__":
    main()
