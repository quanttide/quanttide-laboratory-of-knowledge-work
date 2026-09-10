"""文档解析器：按章程的资产类型，用命名找到一件文档。

资产表见下方 ASSETS——量潮第二大脑章程第九条、第十三条的二十格格子在本仓的落点；
目录名与资产类型一一对应。

命名规则：文件名用英文、篇内标题用中文，二者不互译——所以按名查找同时认文件名与标题。

用法：
  python3 resolver.py 材料        按名查找（认文件名与标题）
  python3 resolver.py 案例 --show 查找并打印内容
  python3 resolver.py --list      列出全部索引
  python3 resolver.py --check     核对资产表在本仓是否齐备
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ASSETS = (
    ("报告", "data/report"),
    ("参考", "data/library"),
    ("历史", "data/history"),
    ("日志", "data/journal"),
    ("档案", "data/profile"),
    ("宣传册", "data/brochure"),
    ("路线图", "data/roadmap"),
    ("洞察", "data/insight"),
    ("意图", "data/intention"),
    ("语境", "data/context"),
    ("归档", "data/archive"),
    ("章程", "docs/bylaw"),
    ("规格", "docs/specification"),
    ("工具箱", "packages/quanttide-work-toolkit"),
    ("手册", "docs/handbook"),
    ("案例", "docs/gallery"),
    ("平台", "apps"),
    ("教程", "docs/tutorial"),
    ("札记", "docs/essay"),
    ("示例", "examples/default"),
)

SKIP = {".git", "node_modules", ".venv", "build", "dist", ".dart_tool", "__pycache__"}


@dataclass
class Entry:
    kind: str
    path: Path
    names: set[str]


def repo_root(start: Path | None = None) -> Path:
    d = (start or Path(__file__)).resolve().parent
    while not (d / "data" / "journal").is_dir():
        if d == d.parent:
            raise FileNotFoundError("未找到 quanttide-work 仓库根")
        d = d.parent
    return d


def title_of(path: Path) -> str | None:
    """篇内标题：正文第一个一级标题。"""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def cn_name(path: Path) -> str | None:
    """仓库的中文名：README 里「量潮知识工作X」。"""
    readme = path / "README.md"
    if not readme.is_file():
        return None
    for line in readme.read_text(encoding="utf-8").splitlines():
        for pattern in (r"^# 量潮知识工作(.+)$", r"量潮知识工作(.{1,8})——"):
            if m := re.match(pattern, line):
                return m.group(1).strip()
    return None


def docs_under(path: Path):
    """资产下的文档：Markdown，跳过构建目录与仓库门面（README/CHANGELOG）。"""
    for md in sorted(path.rglob("*.md")):
        if SKIP & set(md.parts) or md.name in {"README.md", "CHANGELOG.md", "LICENSE"}:
            continue
        yield md


def build_index(root: Path) -> list[Entry]:
    index = []
    for kind, rel in ASSETS:
        path = root / rel
        if not path.is_dir():
            continue
        index.append(Entry(kind, path, {kind, path.name} | ({n} if (n := cn_name(path)) else set())))
        for md in docs_under(path):
            names = {md.stem}
            if title := title_of(md):
                names.add(title)
            index.append(Entry(kind, md, names))
    return index


def find(index: list[Entry], query: str) -> list[Entry]:
    q = query.strip().rstrip("/").lower()
    names = lambda e: {n.lower() for n in e.names}
    exact = [e for e in index if q in names(e)]
    if exact:
        return exact
    return [e for e in index if any(q in n or n in q for n in names(e))]


def main(argv):
    root = repo_root()
    if len(argv) > 1 and argv[1] == "--check":
        missing = [f"{kind}（{rel}）" for kind, rel in ASSETS if not (root / rel).is_dir()]
        print("资产齐备：二十格全在。" if not missing else "缺资产：" + "、".join(missing))
        return 1 if missing else 0

    index = build_index(root)
    if len(argv) < 2 or argv[1] == "--list":
        for entry in index:
            print(f"[{entry.kind}] {entry.path.relative_to(root)}  {'／'.join(sorted(entry.names))}")
        return 0
    query = argv[1]
    matches = find(index, query)
    if not matches:
        print(f"未找到：{query}")
        return 1
    for entry in matches:
        print(f"[{entry.kind}] {entry.path.relative_to(root)}")
        if "--show" in argv[2:]:
            if entry.path.is_dir():
                print("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                print(entry.path.read_text(encoding="utf-8").rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
