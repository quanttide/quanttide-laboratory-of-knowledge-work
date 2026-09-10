"""任务：工作流的一次执行实例。

规格：任务（Task）＝过程的一次执行实例；它跑的是某条工作流（workflow.py）。

<数据仓>/
├── tasks/<任务>.md           这一次的指令：跑哪条工作流、要什么
└── artifacts/<任务>/
    ├── log.jsonl             执行记录：哪一步、什么时候、结果如何、一句话
    ├── report.md             报告（事件）：执行记录 + 闸门项，机器写
    └── history.md            历史（叙事）：人写

人执行的是步骤：走工作流上的某一步，这一步的验收判据当场判（机械）、列给人（闸门），
事实记进流水与报告。同一个工作流可以被执行很多次，每次都是一件新任务。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import checks as checks_layer
from . import records
from . import workflow as workflow_layer

LOG = "log.jsonl"
REPORT = "report.md"
HISTORY = "history.md"
WORKFLOW_LINE = "跑工作流"
TASK_TEMPLATE = """# 任务：{title}

{line}：{flow}

## 目标

{goal}
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Task:
    """一次执行：跑某条工作流，有自己的流水与产物。"""

    root: Path  # 工作区：读材料、核判据
    data: Path  # 数据仓
    name: str

    @property
    def file(self) -> Path:
        return self.data / "tasks" / f"{self.name}.md"

    @property
    def artifacts_dir(self) -> Path:
        return self.data / "artifacts" / self.name

    def artifact(self, kind: str) -> Path:
        return self.artifacts_dir / kind

    def exists(self) -> bool:
        return self.file.is_file()

    def text(self) -> str:
        return self.file.read_text(encoding="utf-8") if self.file.is_file() else ""

    def goal(self) -> str:
        """指令里的目标：## 目标 那一段的正文。"""
        _, marker, tail = self.text().partition("## 目标")
        if not marker:
            return ""
        return tail.split("## ")[0].strip()

    def workflow_name(self) -> str:
        for line in self.text().splitlines():
            if line.startswith(WORKFLOW_LINE):
                return line.split("：", 1)[-1].split(":", 1)[-1].strip()
        return ""

    def workflow(self) -> workflow_layer.Workflow:
        return workflow_layer.open_workflow(self.data, self.workflow_name())

    def steps(self) -> list[workflow_layer.Step]:
        return self.workflow().steps()

    def events(self) -> list[dict]:
        path = self.artifact(LOG)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []

    def done(self) -> set[str]:
        """哪些步骤走过了：流水里成功执行过的、且名字确实是工作流上的步骤。"""
        names = {step.name for step in self.steps()}
        return {event["step"] for event in self.events() if event.get("ok") and event.get("step") in names}

    def next_step(self) -> workflow_layer.Step | None:
        done = self.done()
        return next((step for step in self.steps() if step.name not in done), None)

    def record(self, step: str, detail: str, ok: bool = True) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        with self.artifact(LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "step": step, "detail": detail, "ok": ok}, ensure_ascii=False) + "\n")

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.data)) if path.is_relative_to(self.data) else str(path)


def create(root: Path, data: Path, name: str, workflow_name: str, about: str = "") -> Task:
    """起一件任务：写下指令（跑哪条工作流、要什么），备好产物三家。"""
    task = Task(root, Path(data), name)
    task.file.parent.mkdir(parents=True, exist_ok=True)
    task.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if not task.file.is_file():
        task.file.write_text(TASK_TEMPLATE.format(title=name, line=WORKFLOW_LINE, flow=workflow_name, goal=about or "<这一次要什么，一句话>"), encoding="utf-8")
    if not task.artifact(REPORT).is_file():
        task.artifact(REPORT).write_text(records.report_template(name), encoding="utf-8")
    if not task.artifact(HISTORY).is_file():
        task.artifact(HISTORY).write_text(records.history_template(name), encoding="utf-8")
    task.record("开工", about or f"跑工作流：{workflow_name}")
    return task


def open_task(root: Path, data: Path, name: str) -> Task:
    return Task(root, Path(data), name)


def listing(root: Path, data: Path) -> list[Task]:
    base = Path(data) / "tasks"
    return [Task(root, Path(data), path.stem) for path in sorted(base.glob("*.md"))] if base.is_dir() else []


def execute(task: Task, root: Path, step: str, note: str = "") -> tuple[bool, list[str], list[tuple[str, str, str]]]:
    """走一步：跑那一步的验收判据，记账，写报告。"""
    found = task.workflow().step(step)
    if found is None:
        return False, [f"工作流里没有这一步：{step}"], []
    results, gates = checks_layer.run(root, checks_layer.parse(found.judges, section=None))
    ok = all(passed for _, passed, _ in results)
    detail = note.strip() or ("；".join(item.note for item, _, _ in results) if results else "做完")
    task.record(step, detail, ok=ok)
    write_report(task, gates)
    lines = [f"{'✓' if ok else '✗'} {step}：{detail}"]
    lines += [f"  {'✓' if passed else '✗'} {item.note}（{spec}）" for item, passed, spec in results]
    lines += [f"  ⧗ {item.note}（留给闸门）" for item in gates]
    rows = [(item.note, "✓" if passed else "✗", spec) for item, passed, spec in results]
    return ok, lines, rows + [(item.note, "闸门", "留给人拍板") for item in gates]


def write_report(task: Task, gates: list) -> Path:
    """报告：执行记录（每步一行）+ 闸门项（留给人）。"""
    lines = [f"# 报告：{task.name}", "", "## 执行记录", ""]
    for event in task.events():
        lines.append(f"- {'✓' if event.get('ok') else '✗'} {event['at']}　{event['step']}　{event['detail']}")
    lines += ["", "## 闸门项", ""]
    lines += [f"- ⧗ {item.note}（留给闸门）" for item in gates] or ["- （暂无）"]
    path = task.artifact(REPORT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def narrate(task: Task, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = task.artifact(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(task.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    task.record("历史", words.strip()[:40])


def state_line(task: Task) -> str:
    steps = task.steps()
    if not steps:
        return f"这条工作流没有步骤——在 workflows/{task.workflow_name()}.md 里写「### 步骤名」"
    step = task.next_step()
    return f"下一步：{step.name}" if step else f"{len(steps)} 个步骤都走过了"
