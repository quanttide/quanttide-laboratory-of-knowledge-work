"""动作的结果：命令行与图形界面共用的一层。

每个动作返回一个 Result——`ok` 通不通，`lines` 是命令行要打印的话，
`columns`/`rows` 是界面要画的同一份表格。界面只管画，命令行只管印，
算法只在这里写一遍。

几个动作之间有接口，一件事就是这么串起来的：
  材料（输入）→ 以它立契约 → 核对契约（审查者报告）→ 写进案卷 → 成果登记回工作区。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import checks as checks_layer
from . import material as material_layer
from . import records

MECHANICAL = ("核对", "结论", "说明")
SECTIONS = ("段位", "结论")
CASE_COLUMNS = ("段", "条数", "状态")
LINK = re.compile(r"`([^`]+)`")


@dataclass
class Result:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = field(default_factory=list)


def short(root: Path, path: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def here(root: Path, text: str) -> Path:
    """把记录里写的一个路径，认成盘上的路径（相对工作区或绝对）。"""
    path = Path(text.strip())
    return path if path.is_absolute() else root / path


# ---- 工作区 ----


def catalog(root: Path) -> Result:
    found = catalog_layer.build(root)
    result = Result(columns=("种类", "路径"))
    for entry in found.entries:
        rel = short(root, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
    return result


def catalog_payload(root: Path) -> dict:
    found = catalog_layer.build(root)
    return {
        "root": root.name,
        "count": len(found.entries),
        "entries": [{"kind": e.kind, "path": short(root, e.path), "names": sorted(e.names)} for e in found.entries],
    }


def audit(root: Path, make: bool = False) -> Result:
    """审计工作区：契约有而工作区无、工作区有而契约无；make 为真则补建缺的格子。"""
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    made = assets_layer.make(root, missing) if make else []
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    ok = not (missing or unregistered)
    result = Result(
        ok=ok,
        columns=("问题", "说明"),
        rows=[("缺资产", f"{a.kind}（{a.name}）") for a in missing] + [("未登记", short(root, p)) for p in unregistered],
    )
    result.lines = [f"补建：{short(root, path)}" for path in made]
    result.lines += [f"{kind}：{what}" for kind, what in result.rows]
    if ok:
        result.lines.append("审计通过：二十格齐备，无未登记目录。")
    elif unregistered and not missing:
        result.lines.append("未登记的目录要么属于某一格（改资产表），要么不该在这儿。")
    return result


def audit_payload(root: Path) -> dict:
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    return {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [short(root, path) for path in unregistered],
    }


# ---- 查看 ----


def find(root: Path, name: str, show: bool = False) -> Result:
    if not name.strip():
        return Result(ok=False, lines=["请填要找的名字"])
    matches = catalog_layer.build(root).find(name)
    if not matches:
        return Result(ok=False, lines=[f"未找到：{name}"])
    result = Result()
    for entry in matches:
        rel = short(root, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
        if show:
            if entry.path.is_dir():
                result.lines.append("  （目录）" + "、".join(sorted(p.name for p in entry.path.iterdir() if not p.name.startswith("."))))
            else:
                result.lines.append(entry.path.read_text(encoding="utf-8").rstrip())
    result.columns = ("种类", "路径")
    return result


def material(root: Path, paths: list[str] | None = None) -> Result:
    found = material_layer.materials(root, paths)
    result = Result(columns=("材料", "类型", "阶段", "时间", "来源"))
    for rel, mat in found:
        result.rows.append((rel, mat.type, mat.stage, mat.created_at or "（缺）", mat.source))
        result.lines.append(f"{rel:52} {mat.type:5} {mat.stage:5} {mat.created_at or '（缺）':11} {mat.source}")
        if mat.missing:
            result.ok = False
            result.lines.append(f"缺字段：{rel}——{'、'.join(mat.missing)}")
    if result.ok:
        result.lines.append("阶段由资产位置承担：日志是原始，其余是材料。")
    return result


def material_payload(root: Path, paths: list[str] | None = None) -> dict:
    found = material_layer.materials(root, paths)
    return {"count": len(found), "materials": [{"path": rel, **vars(mat)} for rel, mat in found]}


# ---- 记录：骨架与核对 ----


def new_record(target: Path, template: str, about: str = "") -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先填写到哪个文件"])
    if target.exists():
        return Result(ok=False, lines=[f"已存在：{target}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(records.contract_template(about) if template == "契约" else template, encoding="utf-8")
    return Result(lines=[f"已写：{target}"] + ([f"以 `{about}` 为题"] if about else []))


def new_contract(target: Path, about: str = "") -> Result:
    return new_record(target, "契约", about)


def new_dossier(target: Path, about: str = "") -> Result:
    return new_record(target, records.dossier_template(about), about)


def audit_contract(root: Path, target: Path, into: Path | None = None) -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先选契约文件"])
    if not target.is_file():
        return Result(ok=False, lines=[f"没有这个文件：{target}"])
    missing = records.missing_sections(target, records.CONTRACT_SECTIONS)
    result = Result(ok=not missing, columns=MECHANICAL)
    result.lines += [f"  {'✓' if name not in missing else '✗'} {name}" for name in records.CONTRACT_SECTIONS]
    if missing:
        result.lines.append(f"契约不完整：缺 {'、'.join(missing)}")
        return result
    result.lines.append("契约完整。")
    results, gates = checks_layer.run(root, checks_layer.parse(target.read_text(encoding="utf-8")))
    result.rows = [(item.note, "✓" if ok else "✗", detail) for item, ok, detail in results]
    result.rows += [(item.note, "闸门", "留给人拍板") for item in gates]
    result.ok = all(ok for _, ok, _ in results)
    if results:
        result.lines.append("机械核对：")
        result.lines += [f"  {'✓' if ok else '✗'} {item.note}（{detail}）" for item, ok, detail in results]
    if gates:
        result.lines.append("闸门项（留给人拍板）：")
        result.lines += [f"  - {item.note}" for item in gates]
    if into:
        written = write_review(into, results, gates)
        result.lines.append(f"已写审查者报告：{written}")
    return result


def write_review(dossier: Path, results: list, gates: list) -> Path:
    """把机械核对与闸门项写进案卷的「审查者报告」一节（没有案卷就先起一份）。"""
    if not dossier.is_file():
        dossier.parent.mkdir(parents=True, exist_ok=True)
        dossier.write_text(records.DOSSIER_TEMPLATE, encoding="utf-8")
    body = [f"- {'✓' if ok else '✗'} {item.note}" for item, ok, _ in results]
    body += [f"- ⧗ {item.note}（留给闸门）" for item in gates]
    lines = dossier.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ") and line[3:].strip() == "审查者报告"), None)
    if start is None:
        lines += ["", "## 审查者报告", "", *body]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        lines = lines[: start + 1] + [""] + body + [""] + lines[end:]
    dossier.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return dossier


def audit_dossier(target: Path) -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先选案卷文件"])
    if not target.is_file():
        return Result(ok=False, lines=[f"没有这个文件：{target}"])
    missing = records.missing_sections(target, records.DOSSIER_SECTIONS)
    result = Result(ok=not missing, columns=SECTIONS)
    result.rows = [(name, "✓" if name not in missing else "✗") for name in records.DOSSIER_SECTIONS]
    result.lines += [f"  {mark} {name}" for name, mark in result.rows]
    result.lines.append("案卷完整。" if not missing else f"案卷不完整：缺 {'、'.join(missing)}")
    return result


# ---- 主轴：一件事 ----


def case_new(target: Path, about: str = "") -> Result:
    return new_record(target, records.case_template(about))


def case(root: Path, target: Path) -> Result:
    """看一件事走到哪一步：四段各引用了什么、有没有断链、下一步该做什么。"""
    if not str(target).strip():
        return Result(ok=False, lines=["请先选一件事的文件"])
    if not target.is_file():
        return Result(ok=False, lines=[f"没有这个文件：{target}"])
    missing = records.missing_sections(target, records.CASE_SECTIONS)
    result = Result(ok=not missing, columns=CASE_COLUMNS, lines=[f"一件事：{target}"])
    if missing:
        result.lines.append(f"少段：{'、'.join(missing)}")
    sections = records.read_sections(target)
    broken = []
    for name in records.CASE_SECTIONS:
        items = [item for item in sections.get(name, []) if item]
        dead = [item for item in items if (rel := LINK.search(item)) and not here(root, rel.group(1)).exists()]
        broken += dead
        if dead:
            status = "断链：" + "、".join(LINK.search(item).group(1) for item in dead)
            result.ok = False
        elif items:
            status = "在"
        else:
            status = "空"
        result.lines.append(f"{name}：{len(items)} 条——{status}")
        result.rows.append((name, str(len(items)), status))
    result.lines.append("下一步：" + next_step(sections, broken))
    return result


def next_step(sections: dict[str, list[str]], broken: list[str]) -> str:
    """一件事走到哪，就报下一步该敲什么。"""
    if broken:
        return "先补上断掉的引用，再往下走。"
    if not sections.get("材料"):
        return "先记材料：kg material <路径>"
    if not sections.get("契约"):
        first = LINK.search(sections["材料"][0])
        return f"立契约：kg new-contract <契约.md> --about {first.group(1) if first else '<材料>'}"
    if not sections.get("产出"):
        return "按契约做出来，落到产出那一节。"
    if not sections.get("案卷"):
        return f"把核对结果写进案卷：kg audit-contract {link_of(sections['契约'][0])} --into <案卷.md>"
    return "四段齐了：核对案卷 kg audit-dossier <案卷.md>，再把成果登记回工作区。"


def link_of(item: str) -> str:
    found = LINK.search(item)
    return found.group(1) if found else item.strip("- ")
