#!/usr/bin/env python3
"""启动入口：python3 run.py [--env test] [--config path]。"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import main  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="jump-xiaoe-live-demo 后端")
    parser.add_argument("--env", dest="env_name", default=None, help="环境名：development / test / production")
    parser.add_argument("--config", dest="config_file", default=None, help="直接指定配置文件（跳过 .env 合并）")
    args, _ = parser.parse_known_args()

    main(env_name=args.env_name, config_file=args.config_file)
