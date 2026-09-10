"""目录层：按契约清点仓库里实际有什么，建成名字索引。

目录是快照——仓库变了要重扫；名字索引同时收文件名与篇内标题，
因为命名规则规定英文文件名与中文标题不互译。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import contract

CONTAINERS = ("data", "docs", "packages", "apps", "examples")  # 资产都挂在这五处之下
SKIP = {".git", "node_modules", ".venv", "build", "dist", ".dart_tool", "__pycache__"}
FACADE = {"README.md", "CHANGELOG.md", "LICENSE"}


@dataclass
class Entry:
    kind: str
    path: Path
    names: set[str] = field(default_factory=set)


@dataclass
class Catalog:
    entries: list[Entry] = field(default_factory=list)

    def add(self, kind: str, path: Path, names: set[str]) -> None:
        self.entries.append(Entry(kind, path, names))

    def find(self, query: str) -> list[Entry]:
        q = query.strip().rstrip("/").lower()
        hits = lambda e: {n.lower() for n in e.names}
        exact = [e for e in self.entries if q in hits(e)]
        if exact:
            return exact
        return [e for e in self.entries if any(q in n or n in q for n in hits(e))]

    def dump(self, root: Path, target: Path) -> None:
        """目录的自带格式：JSON——每条含种类、路径与全部名字。"""
        payload = {
            "root": root.name,
            "count": len(self.entries),
            "entries": [
                {
                    "kind": entry.kind,
                    "path": str(entry.path.relative_to(root)) if entry.path.is_relative_to(root) else str(entry.path),
                    "names": sorted(entry.names),
                }
                for entry in self.entries
            ],
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def unregistered(self, root: Path) -> list[Path]:
        """目录有而契约无：未登记在资产表里的顶层目录。"""
        known = {path for asset in contract.assets() for path in contract.locate(root, asset)}
        found = [
            child
            for name in CONTAINERS
            if (parent := root / name).is_dir()
            for child in parent.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
        return sorted(p for p in found if p not in known)


def title_of(path: Path) -> str | None:
    """篇内标题：正文第一个一级标题。"""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def cn_name(path: Path) -> str | None:
    """仓库的中文名：README 里「量潮知识工作X」或首行的量潮品牌名。"""
    readme = path / "README.md"
    if not readme.is_file():
        return None
    for line in readme.read_text(encoding="utf-8").splitlines():
        for pattern in (r"^# (量潮.+)$", r"量潮知识工作(.{1,8})——"):
            if m := re.match(pattern, line):
                return m.group(1).strip()
    return None


def documents(path: Path):
    """资产下的文档：Markdown，跳过构建目录与门面文件。"""
    for md in sorted(path.rglob("*.md")):
        if SKIP & set(md.parts) or md.name in FACADE:
            continue
        yield md


def build(root: Path) -> Catalog:
    catalog = Catalog()
    for asset in contract.assets():
        for path in contract.locate(root, asset):
            names = {asset.kind, asset.name, path.name}
            if alias := cn_name(path):
                names.add(alias)
            catalog.add(asset.kind, path, names)
            for md in documents(path):
                doc_names = {md.stem}
                if title := title_of(md):
                    doc_names.add(title)
                catalog.add(asset.kind, md, doc_names)
    return catalog
