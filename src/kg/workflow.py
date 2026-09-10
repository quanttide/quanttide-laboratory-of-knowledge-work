"""工作流：串联的工作步骤——过程的编排定义，用 YAML 存。

规格：工作流（Workflow）＝过程的编排定义；任务（Task）＝过程的一次执行实例（见 task.py）。

定义要有**固定的意义**，所以是 YAML 而不是散文：字段名、取值、判据种类都由 schema 定死。

<数据仓>/workflows/<名字>.yaml

  name: 课程档案比对
  note: 比对两边的档案
  steps:
    - name: 定位
      what: 把两边的源找齐
      executor: AI          # AI | 人
      judges:
        - kind: 机械
          note: 个人课程档案在
          spec: path:data/profile/iGuo/course/index.md
        - kind: 闸门
          note: 创始人点头（回流与并法怎么定）

判据两种（kind）：机械（带 spec，程序当场判）与闸门（只有 note，留给人）。
执行者默认 AI——要人做的步骤显式写 executor: 人。
"""

from pathlib import Path

import yaml

AI = "AI"
HUMAN = "人"
EXECUTORS = (AI, HUMAN)
KINDS = ("机械", "闸门")


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


class WorkflowError(ValueError):
    """这份文件不像一份工作流。"""


def dump(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200)


def load(path: Path) -> dict:
    """读一份定义：不是映射、缺字段、取值不对，当场报错。"""
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise WorkflowError(f"{Path(path).name} 不是合法的 YAML：{error}") from error
    if not isinstance(payload, dict):
        raise WorkflowError(f"{Path(path).name} 的顶层不是映射（name / steps）")
    if not str(payload.get("name", "")).strip():
        raise WorkflowError(f"{Path(path).name} 少了 name")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise WorkflowError(f"{Path(path).name} 少了 steps（至少一个步骤）")
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or not str(step.get("name", "")).strip():
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤少了 name")
        executor = step.get("executor", AI)
        if executor not in EXECUTORS:
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的 executor 只能是 {' 或 '.join(EXECUTORS)}，实得 {executor!r}")
        judges = step.get("judges") or []
        if not isinstance(judges, list):
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的 judges 应当是列表")
        for judge in judges:
            if not isinstance(judge, dict) or judge.get("kind") not in KINDS:
                raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的判据 kind 只能是 {' 或 '.join(KINDS)}")
            if judge["kind"] == "机械" and not str(judge.get("spec", "")).strip():
                raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的机械判据少了 spec")
    return payload


class Step:
    """一个工作步骤：叫什么、做什么、谁执行、怎么算完。"""

    def __init__(self, payload: dict):
        self.payload = payload

    @property
    def name(self) -> str:
        return str(self.payload.get("name", "")).strip()

    @property
    def what(self) -> str:
        return str(self.payload.get("what", "")).strip()

    @property
    def executor(self) -> str:
        return self.payload.get("executor", AI)

    @property
    def human(self) -> bool:
        return self.executor == HUMAN

    @property
    def judges(self) -> list[dict]:
        return list(self.payload.get("judges") or [])

    @property
    def machine(self) -> list[dict]:
        return [judge for judge in self.judges if judge.get("kind") == "机械"]

    @property
    def gates(self) -> list[dict]:
        return [judge for judge in self.judges if judge.get("kind") == "闸门"]


class Workflow:
    """过程的编排定义：一串步骤。"""

    def __init__(self, data: Path, name: str, payload: dict | None = None):
        self.data = Path(data)
        self.name = name
        self.payload = payload or {}

    @property
    def file(self) -> Path:
        return self.data / "workflows" / f"{self.name}.yaml"

    def exists(self) -> bool:
        return self.file.is_file()

    def reload(self) -> "Workflow":
        if self.exists():
            self.payload = load(self.file)
        return self

    @property
    def note(self) -> str:
        return str(self.payload.get("note", "")).strip()

    def steps(self) -> list[Step]:
        """步骤：按定义里的顺序——这就是「串联」。"""
        return [Step(item) for item in self.payload.get("steps", [])]

    def step(self, name: str) -> Step | None:
        return next((step for step in self.steps() if step.name == name), None)

    def to_yaml(self) -> str:
        return dump(self.payload)


def create(data: Path, name: str, steps: list[str], note: str = "") -> Workflow:
    """写一条工作流：步骤串联，每步给一份判据骨架（执行者默认 AI）。"""
    payload = {
        "name": name,
        "note": note or "步骤串联：写清每步做什么、谁执行、怎么算完。",
        "steps": [
            {
                "name": step,
                "what": f"<{step}这一步做什么>",
                "executor": AI,
                "judges": [
                    {"kind": "机械", "note": "<能写成断言的>", "spec": "path:data/journal/README.md"},
                    {"kind": "闸门", "note": "<只能人拍板的>"},
                ],
            }
            for step in steps
        ],
    }
    flow = Workflow(Path(data), name, payload)
    flow.file.parent.mkdir(parents=True, exist_ok=True)
    flow.file.write_text(flow.to_yaml(), encoding="utf-8")
    return flow


def open_workflow(data: Path, name: str) -> Workflow:
    flow = Workflow(Path(data), name)
    return flow.reload()


def export(flow: Workflow, target: Path) -> Path:
    """把一条工作流存成一份可带走的文件（原样，不改内容）。"""
    target = Path(target)
    if target.is_dir():
        target = target / flow.file.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(flow.to_yaml(), encoding="utf-8")
    return target


def import_workflow(data: Path, source: Path, name: str = "") -> Workflow:
    """把一份工作流导进来：先照 schema 验一遍，再起个名字落进 workflows/。"""
    payload = load(Path(source))
    chosen = (name or str(payload.get("name", "")).strip() or Path(source).stem).strip()
    flow = Workflow(Path(data), chosen)
    if flow.exists():
        raise FileExistsError(f"已经有一条工作流叫「{chosen}」：{flow.file}（换名字用 --as）")
    payload["name"] = chosen
    flow.payload = payload
    flow.file.parent.mkdir(parents=True, exist_ok=True)
    flow.file.write_text(flow.to_yaml(), encoding="utf-8")
    return flow


def listing(data: Path) -> list[Workflow]:
    base = Path(data) / "workflows"
    return [open_workflow(data, path.stem) for path in sorted(base.glob("*.yaml"))] if base.is_dir() else []
