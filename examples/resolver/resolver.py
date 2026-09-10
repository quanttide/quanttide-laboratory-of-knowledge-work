"""文档解析器：按量潮的目录规则，用命名找到一件文档。

目录规则（quanttide-work）：
  data/{产物}/         产物：context、journal、profile、intention、insight、roadmap
  data/{资产}/         资产：archive、brochure、history、library、report
  docs/specification/{piece,process,place}/   概念规格
  docs/handbook/artifacts/                    规范
  docs/gallery/artifacts/                     案例
  docs/gallery/workflows/                     流程案例
  docs/{bylaw,essay,tutorial}/                章程、文集、教程
  examples/default/                           实验室（内部结构自由，这里索引其 examples/ 下各例）

命名规则：文件名用英文、篇内标题用中文，二者不互译——所以按名查找同时认文件名与标题。

用法：
  python3 resolver.py 材料        按名查找（认文件名与标题）
  python3 resolver.py 案例 --show 查找并打印内容
  python3 resolver.py --list      列出全部索引
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PRODUCTS = {"context", "journal", "profile", "intention", "insight", "roadmap"}
DOCS = (("章程", "bylaw"), ("文集", "essay"), ("教程", "tutorial"))
RULES = (
    ("规格", "docs/specification/*/*.md"),
    ("规范", "docs/handbook/artifacts/*.md"),
    ("案例", "docs/gallery/artifacts/*.md"),
    ("流程", "docs/gallery/workflows/*.md"),
    ("实验", "examples/default/examples/*"),
)


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
    """目录的中文名：README 里「量潮知识工作X」的 X（标题形式或「X——」形式）。"""
    readme = path / "README.md"
    if not readme.is_file():
        return None
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.startswith("# 量潮知识工作"):
            return line[len("# 量潮知识工作"):].strip()
        if (m := re.search(r"量潮知识工作(.{1,8})——", line)) and not line.startswith("#"):
            return m.group(1)
    return None


def build_index(root: Path) -> list[Entry]:
    index = []
    for path in sorted((root / "data").glob("*")):
        if path.is_dir():
            names = {path.name} | ({n} if (n := cn_name(path)) else set())
            index.append(Entry("产物" if path.name in PRODUCTS else "资产", path, names))
    for kind, sub in DOCS:
        directory = root / "docs" / sub
        index.append(Entry(kind, directory, {sub, kind} | ({n} if (n := cn_name(directory)) else set())))
        for path in sorted(directory.glob("*.md")):
            if path.name == "README.md":
                continue  # 仓库门面
            index.append(Entry(kind, path, {path.stem} | ({t} if (t := title_of(path)) else set())))
    for kind, pattern in RULES:
        for path in sorted(root.glob(pattern)):
            if path.is_dir():
                index.append(Entry(kind, path, {path.name}))
                continue
            names = {path.stem}
            if title := title_of(path):
                names.add(title)
            index.append(Entry(kind, path, names))
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
