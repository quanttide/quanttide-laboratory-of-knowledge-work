"""一件事：一个对象，从材料走到成果，中途发生的事都记进它的流水。

案子目录（默认落在工作区的 cases/ 之下，可用 --cases 换地方）：

  cases/<名字>/
    ├── case.md        这件事叫什么、要什么
    ├── materials.md   记进来的输入（四字段 + 时间）
    ├── contract.md    约定要什么、怎么验收
    ├── dossier.md     生成者产出 / 审查者报告 / 人类裁决 / 最终成果
    └── log.jsonl      流水：什么时候、做了什么、结果如何

动作都作用在这一件事上，事实自动记进流水——不用手工把结果从这条命令搬到那条命令。
产出只写一处（案卷的「生成者产出」），成果由它收束。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import records

STAGES = ("材料", "契约", "产出", "审查", "裁决", "成果")
CASE_FILE = "case.md"
MATERIALS = "materials.md"
CONTRACT = "contract.md"
DOSSIER = "dossier.md"
LOG = "log.jsonl"
TITLES = {"材料": "材料", "契约": "契约", "产出": "产出", "审查": "审查者报告", "裁决": "人类裁决", "成果": "最终成果"}


def cases_root(root: Path, given: str | Path | None = None) -> Path:
    return Path(given).expanduser().resolve() if given else root / "cases"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass
class Case:
    """一件事：目录在盘上，状态从文件与流水读出来。"""

    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def file(self, name: str) -> Path:
        return self.path / name

    def exists(self) -> bool:
        return self.file(CASE_FILE).is_file()

    def text(self, name: str) -> str:
        path = self.file(name)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def items(self, name: str) -> list[str]:
        """Markdown 列表里的条目。"""
        return [line.strip()[2:].strip() for line in self.text(name).splitlines() if line.strip().startswith("- ")]

    def dossier(self) -> dict[str, list[str]]:
        return records.read_sections(self.file(DOSSIER)) if self.file(DOSSIER).is_file() else {}

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.text(LOG).splitlines() if line.strip()]

    def stages(self) -> dict[str, bool]:
        """六格状态：材料、契约、产出、审查、裁决、成果。"""
        sections = self.dossier()
        return {
            "材料": bool(self.items(MATERIALS)),
            "契约": "## 目标" in self.text(CONTRACT),
            "产出": bool(sections.get("生成者产出")),
            "审查": bool(sections.get("审查者报告")),
            "裁决": bool(sections.get("人类裁决")),
            "成果": bool(sections.get("最终成果")),
        }

    def next_action(self) -> tuple[str, str]:
        """下一步：状态机说了算，程序据此只摆出该做的事。"""
        state = self.stages()
        for action, hint in (
            ("材料", "记一条材料（还没做成成品的输入）"),
            ("契约", "以记下的材料立契约"),
            ("核对", "跑契约的机械核对，结果写进案卷"),
            ("产出", "按契约做出来，记一笔产出"),
            ("裁决", "谁拍板、决定是什么"),
            ("成果", "收尾：把成果写进案卷"),
        ):
            if action == "核对" and state["契约"] and not state["审查"]:
                return action, hint
            if action not in ("核对",) and not state[action]:
                return action, hint
        return "完成", "六格齐了；成果该登记回工作区"

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

    def fill_section(self, title: str, body: list[str]) -> None:
        """把案卷里某一段的正文换掉（其余各段原样留着）。"""
        body = [item if item.startswith("- ") else f"- {item}" for item in body]
        text = self.text(DOSSIER)
        head, marker, tail = text.partition(f"## {title}")
        if marker:
            _, _, rest = tail.partition("## ")
            text = f"{head}## {title}\n\n" + "\n".join(body) + ("\n\n## " + rest if rest else "\n")
        else:
            text = text.rstrip() + f"\n\n## {title}\n\n" + "\n".join(body) + "\n"
        self.write(DOSSIER, text)

    def append_section(self, title: str, item: str) -> None:
        body = self.dossier().get(title, [])
        self.fill_section(title, body + [item])


def create(root: Path, name: str, cases: str | Path | None = None, about: str = "") -> Case:
    """起一件事：建目录，写下抬头与案卷骨架。"""
    case = Case(cases_root(root, cases) / name)
    case.path.mkdir(parents=True, exist_ok=True)
    if not case.file(CASE_FILE).is_file():
        case.write(CASE_FILE, f"# 一件事：{name}\n\n{about}\n" if about else f"# 一件事：{name}\n")
    if not case.file(MATERIALS).is_file():
        case.write(MATERIALS, "# 材料\n")
    if not case.file(DOSSIER).is_file():
        case.write(DOSSIER, f"# 案卷：{name}\n\n## 生成者产出\n\n## 审查者报告\n\n## 人类裁决\n\n## 最终成果\n")
    case.record("起案", about or name)
    return case


def open_case(root: Path, name: str, cases: str | Path | None = None) -> Case:
    return Case(cases_root(root, cases) / name)


def listing(root: Path, cases: str | Path | None = None) -> list[Case]:
    base = cases_root(root, cases)
    return [Case(child) for child in sorted(base.iterdir()) if (child / CASE_FILE).is_file()] if base.is_dir() else []


# ---- 动作：每一步都记进流水 ----


def add_material(case: Case, root: Path, rel: str, fields: str) -> None:
    case.append(MATERIALS, f"`{rel}`　{fields}　（{now()}）")
    case.record("材料", rel)


def write_contract(case: Case, about: str) -> None:
    case.write(CONTRACT, records.contract_template(about))
    case.record("契约", f"以 {about} 为题" if about else "写契约")


def review(case: Case, root: Path) -> tuple[bool, list[str]]:
    """跑契约的机械核对，把结果写进案卷的审查者报告，并记流水。"""
    from . import report

    if not case.file(CONTRACT).is_file():
        return False, ["还没有契约"]
    result = report.audit_contract(root, case.file(CONTRACT))
    body = [f"- {'✓' if mark == '✓' else '✗'} {note}" for note, mark, _ in result.rows if mark != "闸门"]
    body += [f"- ⧗ {note}（留给闸门）" for note, mark, _ in result.rows if mark == "闸门"]
    case.fill_section("审查者报告", body)
    case.record("审查", f"机械核对 {len(result.rows)} 项", ok=result.ok)
    return result.ok, result.lines


def add_output(case: Case, rel: str) -> None:
    case.append_section("生成者产出", f"`{rel}`　（{now()}）")
    case.record("产出", rel)


def decide(case: Case, words: str) -> None:
    case.fill_section("人类裁决", [words])
    case.record("裁决", words)


def finish(case: Case, root: Path) -> list[str]:
    """收尾：把生成者产出收束成最终成果。"""
    body = case.dossier().get("生成者产出", [])
    case.fill_section("最终成果", body or ["（没有产出可收）"])
    case.record("成果", f"{len(body)} 项")
    return body


def state_line(case: Case) -> str:
    """给界面用的一句人话。"""
    action, hint = case.next_action()
    return hint if action == "完成" else f"下一步：{action}——{hint}"
