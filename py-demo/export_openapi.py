#!/usr/bin/env python3
"""导出 OpenAPI 契约到 docs/openapi.json（供 Apifox / Postman 文件导入，或走 GitHub raw 链接）。

用法：
    python3 export_openapi.py                 # 导出到 ../docs/openapi.json
    python3 export_openapi.py out.json        # 指定输出路径
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import load_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join("..", "docs", "openapi.json")
    config = load_settings()
    app = create_app(config, print_banner=False)
    spec = app.openapi()

    directory = os.path.dirname(os.path.abspath(target))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fp:
        json.dump(spec, fp, ensure_ascii=False, indent=2)
        fp.write("\n")

    print("已导出 %s（openapi %s，%d 条路径，servers=%s）" % (
        target, spec.get("openapi"), len(spec.get("paths", {})),
        [s.get("url") for s in spec.get("servers", [])] or "无",
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
