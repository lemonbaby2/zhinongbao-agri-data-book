"""把站点的 JSON 数据打包成 core-data.js。

作用有两个：
1. 让网站直接双击 index.html（file:// 协议）时也能读到核心数据，不必启动服务；
2. 减少 http 模式下的首屏请求数量。

用法：
    python tools/build_core_data.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
OUT = DATA / "core-data.js"
VERSION = "2.2.0"

CORE_FILES = {
    "dashboard": "dashboard.json",
    "crops": "crops.json",
    "tableIndex": "table_index.json",
    "charts": "chart_manifest.json",
    "sourceManifest": "source_manifest.json",
}


def load(name: str) -> object:
    path = DATA / name
    if not path.is_file():
        raise SystemExit(f"缺少数据文件: {path}")
    # ensure_ascii=True 让中文以 \uXXXX 形式写入，避免不同编码环境下读成乱码
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    payload = {key: load(value) for key, value in CORE_FILES.items()}
    payload["build"] = {
        "version": VERSION,
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records": len(payload["dashboard"].get("panel", {}).get("rows", [])),
        "provinces": len(payload["dashboard"].get("provinces", [])),
        "tables": len(payload["tableIndex"]),
        "charts": len(payload["charts"]),
    }
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    header = (
        "/* 由 tools/build_core_data.py 自动生成，请勿手工编辑。\n"
        "   数据来源: site/data/*.json（本机比赛工作簿导出，含 SHA-256 清单） */\n"
    )
    OUT.write_text(f"{header}window.__ZN_CORE__={body};\n", encoding="utf-8")
    size = OUT.stat().st_size / 1024
    print(f"已生成 {OUT.relative_to(ROOT)}  {size:,.0f} KB")
    for key, value in payload.items():
        count = len(value) if hasattr(value, "__len__") else 1
        print(f"  - {key}: {count} 项")


if __name__ == "__main__":
    main()
