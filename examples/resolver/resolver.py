"""文档解析器：按章程的资产类型，用命名找到一件文档。

资产表见下方：章程第九条、第十三条的二十格，中文名是本领域用名，落点按命名规则推导
（文档类 data/ 或 docs/ 同名目录；工具箱、平台、实验室为独立仓库，按 packages/*-toolkit、
apps/*、examples/* 找）。

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

STATED = (  # 陈述型九宫格（章程第十三条）与不占格资产（章程第二条）
    ("报告", "report"),
    ("参考", "library"),
    ("历史", "history"),
    ("日志", "journal"),
    ("档案", "profile"),
    ("宣传册", "brochure"),
    ("路线图", "roadmap"),
    ("洞察", "insight"),
    ("意图", "intention"),
    ("语境", "context"),
    ("归档", "archive"),
)

PROCEDURAL = (  # 程序型九宫格（章程第九条）
    ("章程", "bylaw"),
    ("规格", "specification"),
    ("工具箱", "toolkit"),
    ("手册", "handbook"),
    ("案例", "gallery"),
    ("平台", "platform"),
    ("教程", "tutorial"),
    ("札记", "essay"),
    ("实验室", "example"),
)

LOCATION = {  # 非同名目录的三类，按命名规则找独立仓库
    "toolkit": "packages/*-toolkit",
    "platform": "apps/*",
    "example": "examples/*",
}

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


def locate(root: Path, asset: str) -> list[Path]:
    """资产的落点：文档类入 data/ 或 docs/，独立仓库按 LOCATION 的命名规则找。"""
    for candidate in (root / "data" / asset, root / "docs" / asset):
        if candidate.is_dir():
            return [candidate]
    return sorted(root.glob(LOCATION[asset])) if asset in LOCATION else []


def build_index(root: Path) -> list[Entry]:
    index = []
    for kind, asset in STATED + PROCEDURAL:
        for path in locate(root, asset):
            index.append(Entry(kind, path, {kind, asset, path.name} | ({n} if (n := cn_name(path)) else set())))
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
        missing = [f"{kind}（{asset}）" for kind, asset in STATED + PROCEDURAL if not locate(root, asset)]
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
