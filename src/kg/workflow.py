"""工作流：一串步骤，每步关联一个任务；以及它的一次运行（执行）。

规格：工作流（Workflow）＝过程的编排定义；任务（Task）＝干活的单位（目标 / 步骤 / 验收）。
本程序不预置编排——一次运行的工作流写在自己的现场里，步骤关联哪些任务由现场说了算。

<数据仓>/runs/<名字>/
  ├── workflow.md      本次工作流：步骤清单（- 步骤名 → tasks/<步骤名>.md）
  ├── tasks/<步骤名>.md  每个步骤关联的任务（目标 / 步骤 / 验收）
  └── log.jsonl        执行记录：哪一步、什么时候、结果如何、一句话

<数据仓>/report/<名字>.md   报告（事件）：执行记录与闸门项
<数据仓>/history/<名字>.md  历史（叙事）：人写

人执行的是任务：把某个步骤关联的任务做一次，这一步就算走完；事实记进流水与报告。
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import checks as checks_layer
from . import records

WORKFLOW_FILE = "workflow.md"
TASKS_DIR = "tasks"
LOG = "log.jsonl"
REPORT = "report"
HISTORY = "history"
STEP_LINE = re.compile(r"^\s*-\s*(?P<name>[^→>-]+?)\s*(?:→|->)\s*(?P<task>\S+\.md)\s*$")


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


def runs_root(data: Path, given: str | Path | None = None) -> Path:
    return Path(given).expanduser().resolve() if given else Path(data) / "runs"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass(frozen=True)
class Step:
    """工作流上的一个位置：叫什么，关联哪个任务。"""

    name: str
    task: str  # 相对现场的路径，如 tasks/材料.md


@dataclass
class Run:
    """一次运行：现场在工作区外，记录按资产进格。"""

    root: Path  # 工作区：读材料、核判据
    dir: Path  # 现场
    data: Path  # 数据仓

    @property
    def name(self) -> str:
        return self.dir.name

    def file(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    def record_file(self, kind: str) -> Path:
        return self.data / kind / f"{self.name}.md"

    def exists(self) -> bool:
        return self.file(WORKFLOW_FILE).is_file()

    def text(self, *parts: str) -> str:
        path = self.file(*parts)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def workflow_text(self) -> str:
        return self.text(WORKFLOW_FILE)

    def steps(self) -> list[Step]:
        """工作流上的步骤：按写进 workflow.md 的顺序。"""
        found = []
        for line in self.workflow_text().splitlines():
            if match := STEP_LINE.match(line):
                found.append(Step(match.group("name").strip(), match.group("task").strip()))
        return found

    def task_of(self, step: str) -> Path:
        for item in self.steps():
            if item.name == step:
                return self.file(item.task)
        return self.file(TASKS_DIR, f"{step}.md")

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.text(LOG).splitlines() if line.strip()]

    def done(self) -> set[str]:
        """哪些步骤做过了：流水里成功执行过的、且名字确实是工作流上的步骤。"""
        names = {step.name for step in self.steps()}
        return {event["step"] for event in self.events() if event.get("ok") and event.get("step") in names}

    def next_step(self) -> Step | None:
        done = self.done()
        return next((step for step in self.steps() if step.name not in done), None)

    def record(self, step: str, detail: str, ok: bool = True) -> None:
        with self.file(LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "step": step, "detail": detail, "ok": ok}, ensure_ascii=False) + "\n")


def create(root: Path, name: str, data: Path, steps: list[str] | None = None, runs: str | Path | None = None, about: str = "") -> Run:
    """起一次运行：写下工作流（步骤清单）与每个步骤关联的任务骨架。"""
    run = Run(root, runs_root(data, runs) / name, Path(data))
    run.file(TASKS_DIR).mkdir(parents=True, exist_ok=True)
    chosen = steps or ["材料", "指令", "核对", "产出", "裁决", "成果", "历史"]
    if not run.file(WORKFLOW_FILE).is_file():
        body = [f"# 工作流：{name}", "", about or "本程序不预置编排；步骤与关联的任务由这份文件说了算。", "", "## 步骤", ""]
        body += [f"- {step} → {TASKS_DIR}/{step}.md" for step in chosen]
        run.file(WORKFLOW_FILE).write_text("\n".join(body) + "\n", encoding="utf-8")
    for step in chosen:
        task = run.task_of(step)
        if not task.is_file():
            task.write_text(records.task_template(step, about or "<这一次要什么，一句话>"), encoding="utf-8")
    for path, text in ((run.record_file(REPORT), records.report_template(name)), (run.record_file(HISTORY), records.history_template(name))):
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    run.record("开工", about or "起一次运行")
    return run


def open_run(root: Path, name: str, data: Path, runs: str | Path | None = None) -> Run:
    return Run(root, runs_root(data, runs) / name, Path(data))


def listing(root: Path, data: Path, runs: str | Path | None = None) -> list[Run]:
    base = runs_root(data, runs)
    return [Run(root, child, Path(data)) for child in sorted(base.iterdir()) if (child / WORKFLOW_FILE).is_file()] if base.is_dir() else []


def execute(run: Run, root: Path, step: str, note: str = "") -> tuple[bool, list[str], list[tuple[str, str, str]]]:
    """执行一个步骤：跑它关联任务的验收判据，记账，写报告。"""
    task = run.task_of(step)
    if not task.is_file():
        return False, [f"这一步没有关联的任务：{task}"], []
    text = task.read_text(encoding="utf-8")
    results, gates = checks_layer.run(root, checks_layer.parse(text))
    ok = all(passed for _, passed, _ in results)
    detail = note.strip() or ("；".join(item.note for item, _, _ in results) if results else "做完")
    run.record(step, detail, ok=ok)
    write_report(run, results, gates)
    lines = [f"{'✓' if ok else '✗'} {step}：{detail}"]
    lines += [f"  {'✓' if passed else '✗'} {item.note}（{spec}）" for item, passed, spec in results]
    lines += [f"  ⧗ {item.note}（留给闸门）" for item in gates]
    return ok, lines, [(item.note, "✓" if passed else "✗", spec) for item, passed, spec in results] + [(item.note, "闸门", "留给人拍板") for item in gates]


def write_report(run: Run, results: list, gates: list) -> Path:
    """报告：执行记录（每步一行）+ 闸门项（留给人）。"""
    lines = [f"# 报告：{run.name}", "", "## 执行记录", ""]
    for event in run.events():
        mark = "✓" if event.get("ok") else "✗"
        lines.append(f"- {mark} {event['at']}　{event['step']}　{event['detail']}")
    lines += ["", "## 闸门项", ""]
    lines += [f"- ⧗ {item.note}（留给闸门）" for item in gates] or ["- （暂无）"]
    path = run.record_file(REPORT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def narrate(run: Run, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = run.record_file(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(run.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    run.record("历史", words.strip()[:40])


def state_line(run: Run) -> str:
    step = run.next_step()
    total = len(run.steps())
    if not total:
        return "工作流里还没有步骤——在 workflow.md 里写「- 步骤名 → tasks/步骤名.md」"
    return f"下一步：{step.name}（{step.name} 这一步关联的任务：{step.task}）" if step else f"{total} 个步骤都做过了"
