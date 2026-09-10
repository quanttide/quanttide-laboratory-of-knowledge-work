"""一件事：一个对象，从材料走到成果，中途发生的事落在它身上。

案子目录（默认落在工作区的 cases/ 之下，可用 --cases 换地方）只是一件事的在飞部分；
它的记录按资产进对应的格子——**报告（事件）进 data/report/，历史（叙事）进 data/history/**：

  cases/<名字>/            在飞的：要什么、记了哪些材料、契约、流水
    ├── case.md
    ├── materials.md
    ├── contract.md
    └── log.jsonl
  data/report/<名字>.md    事件：生成者产出 / 审查者报告 / 人类裁决 / 最终成果（机器写）
  data/history/<名字>.md   叙事：这件事的来龙去脉（人写）

动作都作用在这一件事上，事实自动记进流水与报告——不用手工把结果从这条命令搬到那条命令。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import records

STAGES = ("材料", "契约", "核对", "产出", "裁决", "成果", "历史")
CASE_FILE = "case.md"
MATERIALS = "materials.md"
CONTRACT = "contract.md"
LOG = "log.jsonl"
REPORT = "report"
HISTORY = "history"


def cases_root(root: Path, given: str | Path | None = None) -> Path:
    return Path(given).expanduser().resolve() if given else root / "cases"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Case:
    """一件事：在飞的目录在工作区里，记录按资产进格。"""

    root: Path
    dir: Path

    @property
    def name(self) -> str:
        return self.dir.name

    def file(self, name: str) -> Path:
        return self.dir / name

    def record_file(self, kind: str) -> Path:
        """记录落点：报告进 data/report，历史进 data/history。"""
        return self.root / "data" / kind / f"{self.name}.md"

    def exists(self) -> bool:
        return self.file(CASE_FILE).is_file()

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
            ("历史", "写这件事的来龙去脉——报告记事，历史叙事"),
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


def create(root: Path, name: str, cases: str | Path | None = None, about: str = "") -> Case:
    """起一件事：在飞的目录建起来，报告与历史各进对应的格子。"""
    case = Case(root, cases_root(root, cases) / name)
    case.dir.mkdir(parents=True, exist_ok=True)
    if not case.file(CASE_FILE).is_file():
        case.write(CASE_FILE, f"# 一件事：{name}\n\n{about}\n" if about else f"# 一件事：{name}\n")
    if not case.file(MATERIALS).is_file():
        case.write(MATERIALS, "# 材料\n")
    report, history = case.record_file(REPORT), case.record_file(HISTORY)
    for path, text in ((report, records.report_template(name)), (history, records.history_template(name))):
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    case.record("起案", about or name)
    return case


def open_case(root: Path, name: str, cases: str | Path | None = None) -> Case:
    return Case(root, cases_root(root, cases) / name)


def listing(root: Path, cases: str | Path | None = None) -> list[Case]:
    base = cases_root(root, cases)
    return [Case(root, child) for child in sorted(base.iterdir()) if (child / CASE_FILE).is_file()] if base.is_dir() else []


# ---- 动作：每一步都留下痕迹 ----


def add_material(case: Case, rel: str, fields: str) -> None:
    case.append(MATERIALS, f"`{rel}`　{fields}　（{now()}）")
    case.record("材料", rel)


def write_contract(case: Case, about: str) -> None:
    case.write(CONTRACT, records.contract_template(about))
    case.record("契约", f"以 {about} 为题" if about else "写契约")


def review(case: Case, root: Path) -> tuple[bool, list[str]]:
    """跑契约的机械核对，结果写进报告的审查者报告，并记流水。"""
    from . import report

    if not case.file(CONTRACT).is_file():
        return False, ["还没有契约"]
    result = report.audit_contract(root, case.file(CONTRACT))
    body = [f"{'✓' if mark == '✓' else '✗'} {note}" for note, mark, _ in result.rows if mark != "闸门"]
    body += [f"⧗ {note}（留给闸门）" for note, mark, _ in result.rows if mark == "闸门"]
    case.fill_in(case.record_file(REPORT), "审查者报告", body)
    case.record("核对", f"机械核对 {len(result.rows)} 项", ok=result.ok)
    return result.ok, result.lines


def add_output(case: Case, rel: str) -> None:
    case.append_in(case.record_file(REPORT), "生成者产出", f"`{rel}`　（{now()}）")
    case.record("产出", rel)


def decide(case: Case, words: str) -> None:
    case.fill_in(case.record_file(REPORT), "人类裁决", [words])
    case.record("裁决", words)


def finish(case: Case) -> list[str]:
    """收尾：把生成者产出收束成最终成果。"""
    body = case.report().get("生成者产出", [])
    case.fill_in(case.record_file(REPORT), "最终成果", body or ["（没有产出可收）"])
    case.record("成果", f"{len(body)} 项")
    return body


def narrate(case: Case, words: str) -> None:
    """历史只收叙事：一段一段往下写。"""
    path = case.record_file(HISTORY)
    text = path.read_text(encoding="utf-8") if path.is_file() else records.history_template(case.name)
    text = text.replace(records.HISTORY_PLACEHOLDER, "").rstrip()
    path.write_text(f"{text}\n\n{words.strip()}\n", encoding="utf-8")
    case.record("历史", words.strip()[:40])


def state_line(case: Case) -> str:
    """给界面用的一句人话。"""
    action, hint = case.next_action()
    return hint if action == "完成" else f"下一步：{action}——{hint}"
