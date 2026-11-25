# -*- coding: utf-8 -*-
"""同步卷八到内置网页 books_index.json（幂等）。

网页阅读器按 blocks 渲染；卷八每章 20 页，此处将其页内 blocks 展平，
并保留 algo/action 新块型（网页 app.js 已支持通用渲染回退）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / "app" / "data" / "book_data.json"
INDEX = ROOT / "app" / "site" / "data" / "books_index.json"


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    index = json.load(open(INDEX, encoding="utf-8"))
    vol = next(b for b in book["books"] if b["id"] == "vol8")

    chapters = []
    for ch in vol["chapters"]:
        blocks = [b for pg in ch.get("pages", []) for b in pg.get("blocks", [])]
        chapters.append({
            "title": ch["title"],
            "lead": ch.get("lead", ""),
            "blocks": blocks,
        })
    entry = {
        "id": "vol8",
        "title": vol["title"],
        "subtitle": vol.get("subtitle", "决策系统专卷"),
        "icon": vol.get("icon", "🧭"),
        "chapters": chapters,
    }
    index = [b for b in index if b.get("id") != "vol8"] + [entry]
    json.dump(index, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 同步 typography 到网页
    typ = json.load(open(ROOT / "app" / "data" / "typography.json", encoding="utf-8"))
    json.dump(typ, open(ROOT / "app" / "site" / "data" / "typography.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("books_index 卷数:", len(index))
    print("vol8 章数:", len(chapters), "块数:", sum(len(c["blocks"]) for c in chapters))


if __name__ == "__main__":
    main()
