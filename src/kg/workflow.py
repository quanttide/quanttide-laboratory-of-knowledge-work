"""工作流：过程的编排定义——一串标准任务；以及它的一次运行。

规格：工作流（Workflow）是过程的编排定义，以有向无环图描述任务之间的衔接
（`docs/specification/process/workflow.md`）；任务是过程的一次执行实例
（`docs/specification/process/task.md`）。

默认工作流「一次交付」，七个标准任务（线性）：

  材料 → 指令 → 核对 → 产出 → 裁决 → 成果 → 历史

一次运行的现场落在 <数据仓>/runs/<名字>/；记录按资产进格——报告（事件）进 report/、历史（叙事）进 history/：

  runs/<名字>/
    ├── task.md        这一次的指令（目标 / 步骤 / 验收）
    ├── materials.md   记进来的输入
    └── log.jsonl      流水：哪个标准任务、什么时候做的、结果如何
  report/<名字>.md     事件：生成者产出 / 审查者报告 / 人类裁决 / 最终成果（机器写）
  history/<名字>.md    叙事（人写）

标准任务由工作流定义，动作只是把某个标准任务执行一次——执行过的事实自动记进流水与报告。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import records

@dataclass(frozen=True)
class StandardTask:
    """工作流里的一个标准任务：叫什么、干什么、交出什么、怎么算完。"""

    name: str
    what: str
    output: str
    accept: str


@dataclass(frozen=True)
class Workflow:
    """过程的编排定义：一串标准任务（本程序只有一条线性路径）。"""

    name: str
    tasks: tuple[StandardTask, ...]
    note: str = ""


# 默认工作流：一次交付
WORKFLOW = Workflow(
    name="一次交付",
    note="从记下输入到留下记录：七个标准任务，一件工件往下走。",
    tasks=(
        StandardTask("材料", "把还没做成成品的输入记进来", "materials.md 一行", "四字段（类型/阶段/时间/来源）填得出"),
        StandardTask("指令", "写下这一次的指令", "task.md", "三段齐全：目标 / 步骤 / 验收"),
        StandardTask("核对", "按验收跑机械核对", "report.md 的审查者报告", "机械项有结论，闸门项列给人"),
        StandardTask("产出", "把做出来的东西记上", "report.md 的生成者产出", "落在盘上、路径写得清"),
        StandardTask("裁决", "谁拍板、决定是什么", "report.md 的人类裁决", "有人、有决定"),
        StandardTask("成果", "把产出收束成成果", "report.md 的最终成果", "成果由产出收束而来"),
        StandardTask("历史", "写下这一次的来龙去脉", "history.md", "叙事，人写"),
    ),
)

STAGES = tuple(task.name for task in WORKFLOW.tasks)
TASK_FILE = "task.md"
MATERIALS = "materials.md"
LOG = "log.jsonl"
REPORT = "report"
HISTORY = "history"


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


def runs_root(data: Path, given: str | Path | None = None) -> Path:
    return Path(given).expanduser().resolve() if given else Path(data) / "runs"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Run:
    """任务：在飞的目录在工作区里，记录按资产进格。"""

    root: Path  # 工作区：读材料、核契约
    dir: Path  # 在飞的任务目录
    data: Path  # 数据仓：报告与历史进这里

    @property
    def name(self) -> str:
        return self.dir.name

    def file(self, name: str) -> Path:
        return self.dir / name

    def record_file(self, kind: str) -> Path:
        """记录落点：报告进 <数据仓>/report，历史进 <数据仓>/history。"""
        return self.data / kind / f"{self.name}.md"

    def exists(self) -> bool:
        return self.file(TASK_FILE).is_file()

    def text(self, name: str) -> str:
        path = self.file(name)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def items(self, name: str) -> list[str]:
        """Markdown 列表里的条目。"""
        return [line.strip()[2:].strip() for line in self.text(name).splitlines() if line.strip().startswith("- ")]

    def instruction(self) -> dict[str, list[str]]:
        """任务的指令：目标 / 步骤 / 验收（判据住在验收里）。"""
        return records.read_sections(self.file(TASK_FILE))

    def report(self) -> dict[str, list[str]]:
        path = self.record_file(REPORT)
        return records.read_sections(path) if path.is_file() else {}

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.text(LOG).splitlines() if line.strip()]

    def stages(self) -> dict[str, bool]:
        """七个标准任务的状态：材料、契约、核对、产出、裁决、成果、历史。"""
        report = self.report()
        instruction = self.instruction()
        history = self.record_file(HISTORY)
        return {
            "材料": bool(self.items(MATERIALS)),
            "指令": bool(instruction.get("步骤")) and bool(instruction.get("验收")),
            "核对": bool(report.get("审查者报告")),
            "产出": bool(report.get("生成者产出")),
            "裁决": bool(report.get("人类裁决")),
            "成果": bool(report.get("最终成果")),
            "历史": records.prose(history) != "" if history.is_file() else False,
        }

    def next_action(self) -> tuple[str, str]:
        """下一步：状态机说了算，程序据此只摆出该做的事。"""
        state = self.stages()
        for action, hint in (
            ("材料", "记一条材料（还没做成成品的输入）"),
            ("指令", "写指令：目标 / 步骤 / 验收（判据写在验收里）"),
            ("核对", "跑契约的机械核对，结果写进报告"),
            ("产出", "按契约做出来，记一笔产出"),
            ("裁决", "谁拍板、决定是什么"),
            ("成果", "收尾：把产出收束成成果，写进报告"),
            ("历史", "写这个任务的来龙去脉——报告记事，历史叙事"),
        ):
            if not state[action]:
                return action, hint
        return "完成", "七格齐了；报告与历史都在该在的格子里"

    # ---- 写 ----

    def record(self, kind: str, detail: str, ok: bool = True) -> None:
        with self.file(LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "kind": kind, "detail": detail, "ok": ok}, ensure_ascii=False) + "\n")

    def write(self, name: str, text: str) -> None:
        self.file(name).write_text(text, encoding="utf-8")

    def append(self, name: str, item: str) -> None:
        path = self.file(name)
        text = self.text(name) or f"# {name.removesuffix('.md')}\n"
        path.write_text(text.rstrip() + f"\n- {item}\n", encoding="utf-8")

    def fill_in(self, path: Path, title: str, body: list[str]) -> None:
        """把某个文件里某一段的正文换掉（其余各段原样留着）。"""
        body = [item if item.startswith("- ") else f"- {item}" for item in body]
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        head, marker, tail = text.partition(f"## {title}")
        if marker:
            _, _, rest = tail.partition("## ")
            text = f"{head}## {title}\n\n" + "\n".join(body) + ("\n\n## " + rest if rest else "\n")
        else:
            text = text.rstrip() + f"\n\n## {title}\n\n" + "\n".join(body) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append_in(self, path: Path, title: str, item: str) -> None:
        body = records.read_sections(path).get(title, []) if path.is_file() else []
        self.fill_in(path, title, body + [item])


def create(root: Path, name: str, data: Path, cases: str | Path | None = None, about: str = "") -> Run:
    """起一次运行：在飞的目录建起来，报告与历史各进对应的格子。"""
    task = Run(root, runs_root(data, cases) / name, Path(data))
    task.dir.mkdir(parents=True, exist_ok=True)
    if not task.file(TASK_FILE).is_file():
        task.write(TASK_FILE, records.task_template(name, about))
    if not task.file(MATERIALS).is_file():
        task.write(MATERIALS, "# 材料\n")
    report, history = task.record_file(REPORT), task.record_file(HISTORY)
    for path, text in ((report, records.report_template(name)), (history, records.history_template(name))):
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    task.record("开工", about or name)
    return task


def open_run(root: Path, name: str, data: Path, cases: str | Path | None = None) -> Run:
    return Run(root, runs_root(data, cases) / name, Path(data))


def listing(root: Path, data: Path, cases: str | Path | None = None) -> list[Run]:
    base = runs_root(data, cases)
    return [Run(root, child, Path(data)) for child in sorted(base.iterdir()) if (child / TASK_FILE).is_file()] if base.is_dir() else []


# ---- 动作：每一步都留下痕迹 ----


def add_material(task: Run, rel: str, fields: str) -> None:
    task.append(MATERIALS, f"`{rel}`　{fields}　（{now()}）")
    task.record("材料", rel)


def write_instruction(task: Run, goal: str) -> None:
    """写出指令骨架：目标填上，步骤与验收留给你写。"""
    task.write(TASK_FILE, records.task_template(task.name, goal or "<要什么，一句话>"))
    task.record("指令", goal or "写指令（步骤与验收待填）")


def review(task: Run, root: Path) -> tuple[bool, list[str]]:
    """跑契约的机械核对，结果写进报告的审查者报告，并记流水。"""
    from . import report

    if not task.file(TASK_FILE).is_file():
        return False, ["还没有指令"]
    result = report.audit_instruction(root, task.file(TASK_FILE))
    body = [f"{'✓' if mark == '✓' else '✗'} {note}" for note, mark, _ in result.rows if mark != "闸门"]
    body += [f"⧗ {note}（留给闸门）" for note, mark, _ in result.rows if mark == "闸门"]
    task.fill_in(task.record_file(REPORT), "审查者报告", body)
    task.record("核对", f"机械核对 {len(result.rows)} 项", ok=result.ok)
    return result.ok, result.lines


def add_output(task: Run, rel: str) -> None:
    task.append_in(task.record_file(REPORT), "生成者产出", f"`{rel}`　（{now()}）")
    task.record("产出", rel)


def decide(task: Run, words: str) -> None:
    task.fill_in(task.record_file(REPORT), "人类裁决", [words])
    task.record("裁决", words)


def finish(task: Run) -> list[str]:
    """收尾：把生成者产出收束成最终成果。"""
    body = task.report().get("生成者产出", [])
    task.fill_in(task.record_file(REPORT), "最终成果", body or ["（没有产出可收）"])
    task.record("成果", f"{len(body)} 项")
    return body


def narrate(task: Run, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = task.record_file(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(task.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    task.record("历史", words.strip()[:40])


def state_line(task: Run) -> str:
    """给界面用的一句人话。"""
    action, hint = task.next_action()
    return hint if action == "完成" else f"下一步：{action}——{hint}"
