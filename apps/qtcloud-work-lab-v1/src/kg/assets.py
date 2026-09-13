"""资产层：第二大脑应该有什么、叫什么、落在哪。

依据量潮第二大脑章程第九条（程序型）与第十三条（陈述型）、第二条（不占格）；
资产的中文用名是本领域的命名决定，改动即改规范。
"""

from dataclasses import dataclass
from pathlib import Path

STATED = (  # 陈述型九宫格与不占格资产
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

PROCEDURAL = (  # 程序型九宫格
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

LOCATION = {  # 非同名目录的三格，按命名规则找独立仓库
    "toolkit": "packages/*-toolkit",
    "platform": "apps/*",
    "example": "examples/*",
}


@dataclass(frozen=True)
class Asset:
    kind: str  # 中文用名
    name: str  # 章程的英文资产名


def assets() -> list[Asset]:
    return [Asset(kind, name) for kind, name in STATED + PROCEDURAL]


def locate(root: Path, asset: Asset) -> list[Path]:
    """落点：文档类入 data/ 或 docs/ 的同名目录，独立仓库按 LOCATION 找。"""
    for candidate in (root / "data" / asset.name, root / "docs" / asset.name):
        if candidate.is_dir():
            return [candidate]
    return sorted(root.glob(LOCATION[asset.name])) if asset.name in LOCATION else []


def missing(root: Path) -> list[Asset]:
    """资产表有而工作区无的格子。"""
    return [asset for asset in assets() if not locate(root, asset)]


def make(root: Path, wanted: list[Asset] | None = None) -> list[Path]:
    """补建缺的格子：文档类建 data/ 或 docs/ 下的同名目录，各带一份 README。

    独立仓库那三格（工具箱、平台、实验室）不凭空建——它们是另外的仓库。
    """
    stated = {name for _, name in STATED}
    created = []
    for asset in missing(root) if wanted is None else wanted:
        if asset.name in LOCATION:
            continue
        path = root / ("data" if asset.name in stated else "docs") / asset.name
        path.mkdir(parents=True, exist_ok=True)
        readme = path / "README.md"
        if not readme.is_file():
            readme.write_text(f"# 量潮知识工作{asset.kind}\n", encoding="utf-8")
        created.append(path)
    return created


def repo_root(start: Path | None = None) -> Path:
    """工作区根：从起点往上找，直到看见数据层。"""
    d = (start or Path.cwd()).resolve()
    for candidate in (d, *d.parents):
        if (candidate / "data" / "journal").is_dir():
            return candidate
    raise FileNotFoundError("未找到第二大脑仓库根（应在含 data/journal 的目录下使用）")
