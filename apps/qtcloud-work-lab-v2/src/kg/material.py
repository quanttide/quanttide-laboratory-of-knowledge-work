"""材料：还没做成成品的输入——类型、内容、来源、时间。

四字段都能自动填出：类型取扩展名、内容取正文、来源取上级目录与文件名、
时间取文件**自己那个仓库**里首次提交的日期（退回文件名里的日期）。
原始与材料之分不占字段，由资产位置承担：journal 是原始，其余是材料。
这一层是实验室自留——规格未规定。
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

PROSE = ("md", "txt", "rst")  # 正文取首段的一类文件


@dataclass
class Material:
    """一条材料的四字段，外加位置给出的阶段。"""

    type: str
    content: str
    source: str
    created_at: str
    stage: str

    @property
    def missing(self) -> list[str]:
        fields = (("类型", self.type), ("内容", self.content), ("来源", self.source), ("时间", self.created_at))
        return [name for name, value in fields if not value]


def first_seen(path: Path) -> str:
    """时间：优先取文件所在仓库里首次提交的日期，其次取文件名里的日期。"""
    repo = next((item for item in [path.parent, *path.parents] if (item / ".git").exists()), None)
    if repo:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%as", "--", str(path.relative_to(repo))],
            cwd=repo,
            capture_output=True,
            text=True,
        ).stdout.strip().splitlines()
        if out:
            return out[-1]
    digits = [part for part in path.stem.split("-") if part.isdigit()]
    return "-".join(digits[:3]) if len(digits) >= 3 else ""


def stage_of(root: Path, path: Path) -> str:
    """阶段：由资产位置承担——日志是原始，其余是材料。"""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return "材料"
    return "原始" if "journal" in parts else "材料"


def as_material(root: Path, path: Path) -> Material:
    text = path.read_text(encoding="utf-8") if path.suffix.lstrip(".") in PROSE else ""
    body = text.split("\n", 1)[1].strip() if text.startswith("# ") else text.strip()
    content = body[:40].replace("\n", " ") + ("…" if len(body) > 40 else "")
    return Material(
        type=path.suffix.lstrip("."),
        content=content,
        source=f"{path.parent.name}/{path.name}",
        created_at=first_seen(path),
        stage=stage_of(root, path),
    )


def materials(root: Path, rels: list[str] | None = None):
    """逐条读材料：给了路径就看那些，没给就看日志与档案里的文档。"""
    if rels:
        return [(rel, as_material(root, root / rel if not rel.startswith("/") else Path(rel))) for rel in rels]
    found = []
    for kind in ("journal", "profile"):
        base = root / "data" / kind
        if base.is_dir():
            found += [(str(path.relative_to(root)), as_material(root, path)) for path in sorted(base.rglob("*.md"))]
    return found
