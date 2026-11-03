"""把 FastAPI 生成的 OpenAPI 3.1 schema 降级成 3.0.3 可用的形式。

FastAPI 只提供 `app.openapi_version` 这个「改版本号」的属性，不会真的换生成规则，
pydantic v2 仍会吐出 3.1 专属写法。Apifox / Postman 等工具对 3.1 支持不全，导入时常
在这些地方翻车，所以这里统一后处理：

- `anyOf: [X, {"type": "null"}]` → `X` + `nullable: true`
- 多个分支里带 null → 去掉 null 分支，外层加 `nullable: true`
- `const: v` → `enum: [v]`（3.1 关键字，3.0 用 enum 表达）
- `examples: [v]` → `example: v`（3.1 关键字）
"""
from __future__ import annotations

from typing import Any, Dict, List


def _clean(node: Any) -> Any:
    if isinstance(node, list):
        return [_clean(item) for item in node]
    if not isinstance(node, dict):
        return node

    # 先递归处理子结构
    for key, value in list(node.items()):
        if isinstance(value, (dict, list)):
            node[key] = _clean(value)

    # const → enum
    if "const" in node:
        const_value = node.pop("const")
        node.setdefault("enum", [const_value])

    # examples（3.1 数组）→ example
    examples = node.get("examples")
    if isinstance(examples, list) and examples:
        node.pop("examples")
        node.setdefault("example", examples[0])

    # anyOf 里的 null 分支 → nullable
    any_of = node.get("anyOf")
    if isinstance(any_of, list):
        kept = [item for item in any_of if not (isinstance(item, dict) and item.get("type") == "null")]
        if len(kept) != len(any_of):          # 确实含 null 分支
            if len(kept) == 1 and isinstance(kept[0], dict):
                merged = dict(kept[0])
                # 外层原有的其它约束（description/title 等）保留
                for key, value in node.items():
                    if key != "anyOf":
                        merged.setdefault(key, value)
                merged["nullable"] = True
                return merged
            if kept:
                node["anyOf"] = kept
                node["nullable"] = True
            else:
                node.pop("anyOf", None)
                node["nullable"] = True

    return node


def to_openapi_30(spec: Dict[str, Any]) -> Dict[str, Any]:
    """把整份 spec 降级成 OpenAPI 3.0 可用的写法（原地修改并返回）。"""
    cleaned = _clean(spec)
    assert isinstance(cleaned, dict)
    return cleaned


def count_31_markers(spec: Dict[str, Any]) -> List[str]:
    """检查是否还残留 3.1 专属写法（给测试用）。"""
    import json

    raw = json.dumps(spec, ensure_ascii=False)
    markers = []
    if '"type": [' in raw:
        markers.append("type 为数组")
    if '{"type": "null"}' in raw:
        markers.append("type:null 节点")
    if '"const":' in raw:
        markers.append("const 关键字")
    if '"examples": [' in raw:
        markers.append("examples 数组")
    return markers
