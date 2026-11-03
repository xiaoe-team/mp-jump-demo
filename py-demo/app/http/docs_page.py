"""中文版接口文档页（/api/docs）。

Swagger UI 自身只提供英文文案（`swagger-ui-dist` 里没有语言包），这里在 FastAPI 的
Swagger 页上叠一层轻量本地化：把框架文案（Try it out / Schemas / Execute …）替换成中文。
接口的标题、字段说明本来就来自 openapi.json（已是中文），不受影响。

注意：
- Swagger UI 版本固定，文案映射才对得上；升级版本时同步检查 `_LABEL_MAP`。
- 只在普通文本节点上替换，跳过 `<code>` / `<pre>` / `<textarea>`，避免动到示例 JSON。
"""
from __future__ import annotations

SWAGGER_UI_VERSION = "5.34.1"
SWAGGER_JS_URL = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui-bundle.js"
SWAGGER_CSS_URL = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui.css"

# Swagger UI 框架文案 → 中文
_LABEL_MAP = {
    "Try it out": "在线调试",
    "Cancel": "取消",
    "Execute": "发送请求",
    "Clear": "清空",
    "Schemas": "数据模型",
    "Models": "数据模型",
    "Request body": "请求体",
    "Responses": "响应",
    "Response body": "响应体",
    "Parameters": "参数",
    "Parameters ": "参数",
    "Code": "状态码",
    "Example Value": "示例值",
    "Schema": "结构",
    "Media type": "媒体类型",
    "Download": "下载",
    "Authorize": "认证",
    "Available authorizations": "可用认证方式",
    "Close": "关闭",
    "Server": "服务地址",
    "Servers": "服务地址",
    "Expand all": "全部展开",
    "Collapse all": "全部折叠",
    "Details": "详情",
    "Description": "说明",
    "Name": "名称",
    "Required": "必填",
    "required": "必填",
    "Loading...": "加载中…",
    "Filter by tag": "按分组筛选",
    "No operations defined in spec!": "该分组下没有接口",
    "Operations": "接口",
    "Links": "关联",
    "Callbacks": "回调",
}

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} · 接口文档</title>
  <link rel="stylesheet" href="{css_url}" />
  <style>
    body {{ margin: 0; background: #fafafa; }}
    .topbar {{ display: none; }}
  </style>
</head>
<body>
  <div id="swagger-ui"></div>

  <script src="{js_url}" crossorigin></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: "{openapi_url}",
      dom_id: "#swagger-ui",
      deepLinking: true,
      docExpansion: "list",
      defaultModelsExpandDepth: 1,
      displayRequestDuration: true,
      persistAuthorization: false,
      presets: [SwaggerUIBundle.presets.apis],
      layout: "BaseLayout",
      requestInterceptor: function (req) {{
        // 契约里的接口只接受 JSON 请求体
        req.headers["Content-Type"] = "application/json";
        return req;
      }},
    }});

    // ---- 中文文案替换 ----
    (function () {{
      var MAP = {label_map};
      var SKIP = {{ CODE: 1, PRE: 1, TEXTAREA: 1, SCRIPT: 1, STYLE: 1 }};

      function inSkip(node) {{
        var el = node.parentElement;
        while (el) {{
          if (SKIP[el.tagName]) return true;
          el = el.parentElement;
        }}
        return false;
      }}

      function translateNode(node) {{
        if (!node || node.nodeType !== 3) return;
        var raw = node.nodeValue;
        if (!raw) return;
        var key = raw.trim();
        if (!MAP[key] || inSkip(node)) return;
        node.nodeValue = raw.replace(key, MAP[key]);
      }}

      function translateTree(root) {{
        if (!root) return;
        if (root.nodeType === 3) {{ translateNode(root); return; }}
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        var n;
        while ((n = walker.nextNode())) translateNode(n);
      }}

      function boot() {{
        translateTree(document.body);
        new MutationObserver(function (mutations) {{
          mutations.forEach(function (m) {{
            if (m.type !== "childList") return;
            Array.prototype.forEach.call(m.addedNodes, translateTree);
            translateNode(m.target.firstChild || null);
          }});
        }}).observe(document.body, {{ childList: true, subtree: true }});
      }}

      if (document.readyState === "complete") setTimeout(boot, 0);
      else window.addEventListener("load", function () {{ setTimeout(boot, 0); }});
    }})();
  </script>
</body>
</html>
"""


def render_docs_html(title: str, openapi_url: str) -> str:
    """渲染中文版接口文档 HTML。"""
    import json

    label_map = json.dumps(_LABEL_MAP, ensure_ascii=False)
    return _HTML.format(
        title=title,
        css_url=SWAGGER_CSS_URL,
        js_url=SWAGGER_JS_URL,
        openapi_url=openapi_url,
        label_map=label_map,
    )
