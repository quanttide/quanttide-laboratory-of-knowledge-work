"""工作区：工作的边界——根、账本仓与落点。

规格：工作区（Workspace）只认内容、不认位置——工件在物理上从哪来、落在哪，由平台在
装载时决定；同一个工作区，资源可以来自多处、任意组合（见 specification/place/workspace.md）。

本 app 的装载分三处：

- 工作区根（root）：判据路径的基准、`run` 判据的工作目录、工作区级动作（目录 / 审计 /
  材料 / 找文档）扫描的面；默认从当前目录往上找到含 `data/journal` 的第二大脑；
- 账本仓（data）：工作区身份、工单、产物与事件落在这里；默认本 app 的 `data/`；
- 定义目录（workflows）：工作流定义所在；默认 `<账本仓>/workflows/`，可另指一处固定资产目录。

身份缺则首跑生成：`id` / `name` / `title` / `description` / `created_at` / `updated_at`。
位置不进模型：这些都不写进工单文件，只由启动参数定。
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
    """账本仓缺省：本 app 的 `data/`（工作纪律：数据全落这里）。"""
    return Path(__file__).resolve().parents[2] / "data"


def repo_root(start: Path | None = None) -> Path:
    """工作区根缺省：从起点往上找，直到看见数据层（含 `data/journal` 的目录）。"""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "data" / "journal").is_dir():
            return candidate
    return here


def resolve(root=None, data=None, workflows=None) -> "Workspace":
    """装载工作区：位置由启动参数定，缺省按上面的规矩找。

    给了 `--root` 就自成一区（账本仓默认跟着它）；不给则扫面取第二大脑、账本仓取本 app `data/`。
    """
    base = Path(root).expanduser() if root else repo_root()
    if data:
        home = Path(data).expanduser()
    elif root:
        home = base
    else:
        home = lab_data()
    return Workspace(base, home, Path(workflows).expanduser() if workflows else None)


def default_identity(data: Path) -> dict:
    name = data.name if data.name != "data" else data.parent.name
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
    """一次装载：根、账本仓、定义目录。"""

    def __init__(self, root: Path, data: Path | None = None, workflows: Path | None = None):
        self.root = Path(root)
        self.data = Path(data) if data else self.root
        self._workflows = Path(workflows) if workflows else None

    @property
    def identity_file(self) -> Path:
        return self.data / IDENTITY

    @property
    def workflows_dir(self) -> Path:
        return self._workflows or self.data / WORKFLOWS

    @property
    def workorders_dir(self) -> Path:
        return self.data / WORKORDERS

    @property
    def artifacts_dir(self) -> Path:
        return self.data / ARTIFACTS

    @property
    def events_file(self) -> Path:
        return self.data / EVENTS

    def ensure(self) -> "Workspace":
        """写动作前把账本仓开出来：身份缺则首跑生成。只读动作不碰盘。"""
        self.workorders_dir.mkdir(parents=True, exist_ok=True)
        if self._workflows is None:
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
        if not self.identity_file.is_file():
            self.identity_file.write_text(dump(default_identity(self.data)), encoding="utf-8")
        return self

    def identity(self) -> dict:
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
