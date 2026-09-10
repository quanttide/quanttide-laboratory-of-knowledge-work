"""工作流：一串步骤，每步关联一个任务；以及它的一次运行（执行）。

规格：工作流（Workflow）＝过程的编排定义；任务（Task）＝干活的单位（目标 / 步骤 / 验收）。
程序不预置编排——一次运行的工作流写在自己的文件里，步骤关联哪些任务由它说了算。

<数据仓>/
├── workflows/<运行>.md            工作流：步骤清单（- 步骤名 → tasks/<运行>/<步骤名>.md）
├── tasks/<运行>/<步骤名>.md        每个步骤关联的任务（目标 / 步骤 / 验收）
└── artifacts/<运行>/
    ├── log.jsonl                  执行记录：哪一步、什么时候、结果如何、一句话
    ├── report.md                  报告（事件）：执行记录 + 闸门项，机器写
    └── history.md                 历史（叙事）：人写

目录按领域模型分三家：workflows（过程·定义侧）、tasks（过程·执行侧）、artifacts（产物）。
人执行的是任务：把某个步骤关联的任务做一次，这一步就走完；事实记进流水与报告。
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import checks as checks_layer
from . import records

WORKFLOWS = "workflows"
TASKS = "tasks"
ARTIFACTS = "artifacts"
LOG = "log.jsonl"
REPORT = "report.md"
HISTORY = "history.md"
STEP_LINE = re.compile(r"^\s*-\s*(?P<name>[^→>-]+?)\s*(?:→|->)\s*(?P<task>\S+\.md)\s*$")


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass(frozen=True)
class Step:
    """工作流上的一个位置：叫什么，关联哪个任务。"""

    name: str
    task: str  # 相对数据仓的路径，如 tasks/数据归仓/材料.md


@dataclass
class Run:
    """一次运行：工作流、任务、产物分放在数据仓的三家里。"""

    root: Path  # 工作区：读材料、核判据
    data: Path  # 数据仓
    name: str

    @property
    def workflow_file(self) -> Path:
        return self.data / WORKFLOWS / f"{self.name}.md"

    @property
    def tasks_dir(self) -> Path:
        return self.data / TASKS / self.name

    @property
    def artifacts_dir(self) -> Path:
        return self.data / ARTIFACTS / self.name

    def artifact(self, kind: str) -> Path:
        return self.artifacts_dir / kind

    def exists(self) -> bool:
        return self.workflow_file.is_file()

    def workflow_text(self) -> str:
        return self.workflow_file.read_text(encoding="utf-8") if self.workflow_file.is_file() else ""

    def steps(self) -> list[Step]:
        """工作流上的步骤：按写进工作流文件的顺序。"""
        found = []
        for line in self.workflow_text().splitlines():
            if match := STEP_LINE.match(line):
                found.append(Step(match.group("name").strip(), match.group("task").strip()))
        return found

    def task_of(self, step: str) -> Path:
        for item in self.steps():
            if item.name == step:
                return self.data / item.task
        return self.tasks_dir / f"{step}.md"

    def events(self) -> list[dict]:
        path = self.artifact(LOG)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []

    def done(self) -> set[str]:
        """哪些步骤做过了：流水里成功执行过的、且名字确实是工作流上的步骤。"""
        names = {step.name for step in self.steps()}
        return {event["step"] for event in self.events() if event.get("ok") and event.get("step") in names}

    def next_step(self) -> Step | None:
        done = self.done()
        return next((step for step in self.steps() if step.name not in done), None)

    def record(self, step: str, detail: str, ok: bool = True) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        with self.artifact(LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "step": step, "detail": detail, "ok": ok}, ensure_ascii=False) + "\n")

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.data)) if path.is_relative_to(self.data) else str(path)


def create(root: Path, name: str, data: Path, steps: list[str] | None = None, about: str = "") -> Run:
    """起一次运行：写下工作流（步骤清单）与每个步骤关联的任务骨架。"""
    run = Run(root, Path(data), name)
    run.tasks_dir.mkdir(parents=True, exist_ok=True)
    run.artifacts_dir.mkdir(parents=True, exist_ok=True)
    run.workflow_file.parent.mkdir(parents=True, exist_ok=True)
    chosen = [step for step in (steps or DEFAULT_STEPS) if step]
    if not run.workflow_file.is_file():
        body = [f"# 工作流：{name}", "", about or "程序不预置编排；步骤与关联的任务由这份文件说了算。", "", "## 步骤", ""]
        body += [f"- {step} → {run.relative(run.tasks_dir / f'{step}.md')}" for step in chosen]
        run.workflow_file.write_text("\n".join(body) + "\n", encoding="utf-8")
    for step in chosen:
        task = run.task_of(step)
        if not task.is_file():
            task.parent.mkdir(parents=True, exist_ok=True)
            task.write_text(records.task_template(step, about or "<这一次要什么，一句话>"), encoding="utf-8")
    if not run.artifact(REPORT).is_file():
        run.artifact(REPORT).write_text(records.report_template(name), encoding="utf-8")
    if not run.artifact(HISTORY).is_file():
        run.artifact(HISTORY).write_text(records.history_template(name), encoding="utf-8")
    run.record("开工", about or "起一次运行")
    return run


DEFAULT_STEPS = ("材料", "指令", "核对", "产出", "裁决", "成果", "历史")


def open_run(root: Path, name: str, data: Path) -> Run:
    return Run(root, Path(data), name)


def listing(root: Path, data: Path) -> list[Run]:
    base = Path(data) / WORKFLOWS
    return [Run(root, Path(data), path.stem) for path in sorted(base.glob("*.md"))] if base.is_dir() else []


def execute(run: Run, root: Path, step: str, note: str = "") -> tuple[bool, list[str], list[tuple[str, str, str]]]:
    """执行一个步骤：跑它关联任务的验收判据，记账，写报告。"""
    task = run.task_of(step)
    if not task.is_file():
        return False, [f"这一步没有关联的任务：{task}"], []
    results, gates = checks_layer.run(root, checks_layer.parse(task.read_text(encoding="utf-8")))
    ok = all(passed for _, passed, _ in results)
    detail = note.strip() or ("；".join(item.note for item, _, _ in results) if results else "做完")
    run.record(step, detail, ok=ok)
    write_report(run, gates)
    lines = [f"{'✓' if ok else '✗'} {step}：{detail}"]
    lines += [f"  {'✓' if passed else '✗'} {item.note}（{spec}）" for item, passed, spec in results]
    lines += [f"  ⧗ {item.note}（留给闸门）" for item in gates]
    rows = [(item.note, "✓" if passed else "✗", spec) for item, passed, spec in results]
    return ok, lines, rows + [(item.note, "闸门", "留给人拍板") for item in gates]


def write_report(run: Run, gates: list) -> Path:
    """报告：执行记录（每步一行）+ 闸门项（留给人）。"""
    lines = [f"# 报告：{run.name}", "", "## 执行记录", ""]
    for event in run.events():
        lines.append(f"- {'✓' if event.get('ok') else '✗'} {event['at']}　{event['step']}　{event['detail']}")
    lines += ["", "## 闸门项", ""]
    lines += [f"- ⧗ {item.note}（留给闸门）" for item in gates] or ["- （暂无）"]
    path = run.artifact(REPORT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def narrate(run: Run, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = run.artifact(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(run.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    run.record("历史", words.strip()[:40])


def state_line(run: Run) -> str:
    steps = run.steps()
    if not steps:
        step = run.next_step()
        return "工作流里还没有步骤——在 workflows/%s.md 里写「- 步骤名 → tasks/%s/步骤名.md」" % (run.name, run.name)
    step = run.next_step()
    return f"下一步：{step.name}（关联的任务：{run.relative(run.task_of(step.name))}）" if step else f"{len(steps)} 个步骤都做过了"
