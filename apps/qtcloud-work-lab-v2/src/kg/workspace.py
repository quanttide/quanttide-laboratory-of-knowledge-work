"""工作区：工作的边界——身份与落点。

规格：工作区（Workspace）只认内容、不认位置（见 specification/place/workspace.md）。
本 app 里，工作区就是装着 `workspace.yaml` 的那个目录：定义（workflows/）、账本
（workorders/）、产物（artifacts/）与事件（events.jsonl）都落在它下面，不写它外面。

身份缺则首跑生成：`id` / `name` / `title` / `description` / `created_at` / `updated_at`。
"""

from pathlib import Path

import yaml

from . import clock, ids

IDENTITY = "workspace.yaml"
WORKFLOWS = "workflows"
WORKORDERS = "workorders"
ARTIFACTS = "artifacts"
EVENTS = "events.jsonl"
FIELDS = ("id", "name", "title", "description", "created_at", "updated_at")


class WorkspaceError(ValueError):
    """这个工作区不成形。"""


def dump(payload: dict) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=200)


def lab_data() -> Path:
    """实验室自己的工作区：本 app 的 `data/`（工作纪律：数据全落这里）。"""
    return Path(__file__).resolve().parents[2] / "data"


def resolve(where=None) -> "Workspace":
    """工作区不进命令行：从当前目录往上找 `workspace.yaml`，找不到就用实验室 `data/`。

    首跑生成：不存在的目录也要开成工作区（身份与目录在此落成）。
    """
    if where:
        return Workspace(Path(where).expanduser()).ensure()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / IDENTITY).is_file():
            return Workspace(candidate).ensure()
    return Workspace(lab_data()).ensure()


def default_identity(root: Path) -> dict:
    """首跑生成的身份：名字取目录名（`data/` 取上一层），标题同名字。"""
    name = root.name if root.name != "data" else root.parent.name
    stamp = clock.now()
    return {
        "id": ids.new_id(),
        "name": name,
        "title": name,
        "description": "",
        "created_at": stamp,
        "updated_at": stamp,
    }


class Workspace:
    """装着 `workspace.yaml` 的那个目录。"""

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def identity_file(self) -> Path:
        return self.root / IDENTITY

    @property
    def workflows_dir(self) -> Path:
        return self.root / WORKFLOWS

    @property
    def workorders_dir(self) -> Path:
        return self.root / WORKORDERS

    @property
    def artifacts_dir(self) -> Path:
        return self.root / ARTIFACTS

    @property
    def events_file(self) -> Path:
        return self.root / EVENTS

    def ensure(self) -> "Workspace":
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.workorders_dir.mkdir(parents=True, exist_ok=True)
        if not self.identity_file.is_file():
            self.identity_file.write_text(dump(default_identity(self.root)), encoding="utf-8")
        return self

    def identity(self) -> dict:
        """工作区身份：缺则首跑生成，读不通当场报错。"""
        self.ensure()
        try:
            payload = yaml.safe_load(self.identity_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise WorkspaceError(f"{self.identity_file} 不是合法的 YAML：{error}") from error
        if not isinstance(payload, dict):
            raise WorkspaceError(f"{self.identity_file} 的顶层不是映射")
        unknown = [key for key in payload if key not in FIELDS]
        if unknown:
            raise WorkspaceError(f"{self.identity_file} 有不认识的字段：{'、'.join(unknown)}")
        return payload

    def workspace_id(self) -> str:
        return str(self.identity().get("id", ""))
