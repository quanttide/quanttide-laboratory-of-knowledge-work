"""工作流：串联的工作步骤——过程的编排定义，用 YAML 存。

规格：工作流（Workflow）＝过程的编排定义；任务（Task）＝过程的一次执行实例（见 task.py）。

定义要有**固定的意义**，所以是 YAML 而不是散文：字段名、字段取值、判据种类都由 schema 定死，不认识的字段直接报错。

<数据仓>/workflows/<名字>.yaml

  name: 课程档案比对
  description: 比对两边的档案
  steps:
    - name: 定位
      what: 把两边的源找齐
      executor: 智能体
      criteria:
        - type: rule
          note: 个人课程档案在
          spec: path:data/profile/iGuo/course/index.md
        - type: human
          note: 创始人点头（回流与并法怎么定）
"""

from pathlib import Path

import yaml

AGENT = "agent"
HUMAN = "human"
RULE = "rule"
EXECUTORS = (AGENT, HUMAN)
TYPES = (RULE, AGENT, HUMAN)
TOP_FIELDS = ("name", "description", "steps")
STEP_FIELDS = ("name", "what", "executor", "criteria")
CRITERION_FIELDS = ("type", "note", "spec")


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
    unknown = [key for key in payload if key not in TOP_FIELDS]
    if unknown:
        raise WorkflowError(f"{Path(path).name} 顶层有不认识的字段：{'、'.join(unknown)}（只认 {'、'.join(TOP_FIELDS)}）")
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or not str(step.get("name", "")).strip():
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤少了 name")
        extra = [key for key in step if key not in STEP_FIELDS]
        if extra:
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤有不认识的字段：{'、'.join(extra)}（只认 {'、'.join(STEP_FIELDS)}）")
        executor = step.get("executor", AGENT)
        if executor not in EXECUTORS:
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的 executor 只能是 {' 或 '.join(EXECUTORS)}，实得 {executor!r}")
        criteria = step.get("criteria") or []
        if not isinstance(criteria, list):
            raise WorkflowError(f"{Path(path).name} 第 {index} 个步骤的 criteria 应当是列表")
        for order, criterion in enumerate(criteria, start=1):
            where = f"第 {index} 个步骤第 {order} 条判据"
            if not isinstance(criterion, dict) or criterion.get("type") not in TYPES:
                raise WorkflowError(f"{Path(path).name} {where}的 type 只能是 {' / '.join(TYPES)}")
            odd = [key for key in criterion if key not in CRITERION_FIELDS]
            if odd:
                raise WorkflowError(f"{Path(path).name} {where}有不认识的字段：{'、'.join(odd)}（只认 {'、'.join(CRITERION_FIELDS)}）")
            if not str(criterion.get("note", "")).strip():
                raise WorkflowError(f"{Path(path).name} {where}少了 note")
            if criterion["type"] == RULE and not str(criterion.get("spec", "")).strip():
                raise WorkflowError(f"{Path(path).name} {where}是 rule，必须带 spec")
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
        return self.payload.get("executor", AGENT)

    @property
    def human(self) -> bool:
        return self.executor == HUMAN

    @property
    def criteria(self) -> list[dict]:
        return list(self.payload.get("criteria") or [])

    def of(self, kind: str) -> list[dict]:
        return [criterion for criterion in self.criteria if criterion.get("type") == kind]

    @property
    def rules(self) -> list[dict]:
        return self.of(RULE)

    @property
    def agents(self) -> list[dict]:
        return self.of(AGENT)

    @property
    def gates(self) -> list[dict]:
        return self.of(HUMAN)


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
    def description(self) -> str:
        return str(self.payload.get("description", "")).strip()

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
        "description": note or "步骤串联：写清每步做什么、谁执行、怎么判。",
        "steps": [
            {
                "name": step,
                "what": f"<{step}这一步做什么>",
                "executor": AGENT,
                "criteria": [
                    {"type": RULE, "note": "<能写成断言的>", "spec": "path:data/journal/README.md"},
                    {"type": HUMAN, "note": "<只能人拍板的>"},
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
