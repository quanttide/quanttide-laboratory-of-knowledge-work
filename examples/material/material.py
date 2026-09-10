"""材料字段确认：拿真实材料试装四字段——类型、内容、来源、时间。

材料 = 还没做成成品的输入。本脚本从仓库里取真实材料，逐条尝试填满四个字段，
并报告填不出来或缺什么——填不上的地方就是字段要改的地方。

用法：
  python3 material.py          试装并报告
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

SAMPLES = (
    "data/profile/iGuo/course/knowledge-work.md",   # 粗加工后的档案材料
    "data/profile/iGuo/course/production-internship.md",
    "data/profile/iGuo/org.md",
    "data/journal/iGuo/2026-09-10.md",              # 现场记录，偏原始
    "examples/default/examples/default-module/default.md",  # 实验室里的设计稿
)


@dataclass
class Material:
    """材料四字段：类型、内容、来源、时间。"""

    type: str
    content: str
    source: str
    created_at: str

    @property
    def missing(self) -> list[str]:
        return [name for name, value in (("类型", self.type), ("内容", self.content), ("来源", self.source), ("时间", self.created_at)) if not value]


def repo_root(start: Path | None = None) -> Path:
    d = (start or Path(__file__)).resolve().parent
    while not (d / "data" / "journal").is_dir():
        if d == d.parent:
            raise FileNotFoundError("未找到仓库根")
        d = d.parent
    return d


def first_seen(path: Path) -> str:
    """时间：优先取文件所在仓库里首次提交的日期，其次取文件名里的日期。"""
    repo = next((d for d in [path.parent, *path.parents] if (d / ".git").exists()), None)
    if repo:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%as", "--", str(path.relative_to(repo))],
            cwd=repo, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        if out:
            return out[-1]
    digits = [t for t in path.stem.split("-") if t.isdigit()]
    return "-".join(digits[:3]) if len(digits) >= 3 else ""


def as_material(root: Path, rel: str) -> Material:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    body = text.split("\n", 1)[1].strip() if text.startswith("# ") else text.strip()
    return Material(
        type=path.suffix.lstrip("."),
        content=body[:40].replace("\n", " ") + ("…" if len(body) > 40 else ""),
        source=f"{path.parent.name}/{path.name}",
        created_at=first_seen(path),
    )


def main():
    root = repo_root()
    print(f"{'材料':52} 类型   阶段   时间        来源")
    gaps = []
    for rel in SAMPLES:
        material = as_material(root, rel)
        stage = "原始" if rel.startswith("data/journal/") else "材料"
        print(f"{rel:52} {material.type:6} {stage:6} {material.created_at or '（缺）':11} {material.source}")
        if material.missing:
            gaps.append((rel, material.missing))
    print("\n阶段：由资产位置推断——journal 是原始，profile 等是材料。")
    print("\n缺口：")
    if not gaps:
        print("- 四字段都能从真实材料里自动填出。")
    for rel, missing in gaps:
        print(f"- {rel}：缺 {'、'.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
