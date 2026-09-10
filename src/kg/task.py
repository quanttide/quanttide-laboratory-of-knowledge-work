"""任务：一个对象，从材料走到成果，中途发生的事落在它身上。

任务目录（默认落在工作区的 tasks/ 之下，可用 --cases 换地方）只是任务的在飞部分；
它的记录按资产进对应的格子——**报告（事件）进 data/report/，历史（叙事）进 data/history/**：

  tasks/<名字>/            在飞的：要什么、记了哪些材料、契约、流水
    ├── task.md
    ├── materials.md
    ├── contract.md
    └── log.jsonl
  data/report/<名字>.md    事件：生成者产出 / 审查者报告 / 人类裁决 / 最终成果（机器写）
  data/history/<名字>.md   叙事：这个任务的来龙去脉（人写）

动作都作用在这任务上，事实自动记进流水与报告——不用手工把结果从这条命令搬到那条命令。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import records

STAGES = ("材料", "契约", "核对", "产出", "裁决", "成果", "历史")
TASK_FILE = "task.md"
MATERIALS = "materials.md"
CONTRACT = "contract.md"
LOG = "log.jsonl"
REPORT = "report"
HISTORY = "history"


def lab_data() -> Path:
    """数据仓：实验室的 data/——工作纪律：所有数据放这里（见 AGENTS.md）。"""
    return Path(__file__).resolve().parents[2] / "data"


def tasks_root(data: Path, given: str | Path | None = None) -> Path:
    return Path(given).expanduser().resolve() if given else Path(data) / "tasks"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Task:
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

    def report(self) -> dict[str, list[str]]:
        path = self.record_file(REPORT)
        return records.read_sections(path) if path.is_file() else {}

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.text(LOG).splitlines() if line.strip()]

    def stages(self) -> dict[str, bool]:
        """七格状态：材料、契约、核对、产出、裁决、成果、历史。"""
        report = self.report()
        history = self.record_file(HISTORY)
        return {
            "材料": bool(self.items(MATERIALS)),
            "契约": "## 目标" in self.text(CONTRACT),
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
            ("契约", "以记下的材料立契约"),
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


def create(root: Path, name: str, data: Path, cases: str | Path | None = None, about: str = "") -> Task:
    """起任务：在飞的目录建起来，报告与历史各进对应的格子。"""
    task = Task(root, tasks_root(data, cases) / name, Path(data))
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


def open_task(root: Path, name: str, data: Path, cases: str | Path | None = None) -> Task:
    return Task(root, tasks_root(data, cases) / name, Path(data))


def listing(root: Path, data: Path, cases: str | Path | None = None) -> list[Task]:
    base = tasks_root(data, cases)
    return [Task(root, child, Path(data)) for child in sorted(base.iterdir()) if (child / TASK_FILE).is_file()] if base.is_dir() else []


# ---- 动作：每一步都留下痕迹 ----


def add_material(task: Task, rel: str, fields: str) -> None:
    task.append(MATERIALS, f"`{rel}`　{fields}　（{now()}）")
    task.record("材料", rel)


def write_contract(task: Task, about: str) -> None:
    task.write(CONTRACT, records.contract_template(about))
    task.record("契约", f"以 {about} 为题" if about else "写契约")


def review(task: Task, root: Path) -> tuple[bool, list[str]]:
    """跑契约的机械核对，结果写进报告的审查者报告，并记流水。"""
    from . import report

    if not task.file(CONTRACT).is_file():
        return False, ["还没有契约"]
    result = report.audit_contract(root, task.file(CONTRACT))
    body = [f"{'✓' if mark == '✓' else '✗'} {note}" for note, mark, _ in result.rows if mark != "闸门"]
    body += [f"⧗ {note}（留给闸门）" for note, mark, _ in result.rows if mark == "闸门"]
    task.fill_in(task.record_file(REPORT), "审查者报告", body)
    task.record("核对", f"机械核对 {len(result.rows)} 项", ok=result.ok)
    return result.ok, result.lines


def add_output(task: Task, rel: str) -> None:
    task.append_in(task.record_file(REPORT), "生成者产出", f"`{rel}`　（{now()}）")
    task.record("产出", rel)


def decide(task: Task, words: str) -> None:
    task.fill_in(task.record_file(REPORT), "人类裁决", [words])
    task.record("裁决", words)


def finish(task: Task) -> list[str]:
    """收尾：把生成者产出收束成最终成果。"""
    body = task.report().get("生成者产出", [])
    task.fill_in(task.record_file(REPORT), "最终成果", body or ["（没有产出可收）"])
    task.record("成果", f"{len(body)} 项")
    return body


def narrate(task: Task, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = task.record_file(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(task.name)
    text = "\n".join(line for line in text.splitlines() if not (line.strip().startswith("（") and line.strip().endswith("）"))).rstrip()
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    task.record("历史", words.strip()[:40])


def state_line(task: Task) -> str:
    """给界面用的一句人话。"""
    action, hint = task.next_action()
    return hint if action == "完成" else f"下一步：{action}——{hint}"
