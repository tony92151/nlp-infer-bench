#!/usr/bin/env python
"""Helper script to trigger model conversion from the command line."""

from __future__ import annotations

import argparse

from nlp_infer_bench.conversion import convert_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert and upload models")
    parser.add_argument("config", type=str, help="Path to experiment config")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Do not upload converted artifacts to S3",
    )
    args = parser.parse_args()
    convert_models(args.config, upload=not args.skip_upload)


if __name__ == "__main__":
    main()
