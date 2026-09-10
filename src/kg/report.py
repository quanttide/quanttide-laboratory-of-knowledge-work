"""动作的结果：命令行与图形界面共用的一层。

每个动作返回一个 Result——`ok` 通不通，`lines` 是命令行要打印的话，
`columns`/`rows` 是界面要画的同一份表格。界面只管画，命令行只管印，
算法只在这里写一遍。
"""

from dataclasses import dataclass, field
from pathlib import Path

from . import assets as assets_layer
from . import catalog as catalog_layer
from . import checks as checks_layer
from . import material as material_layer
from . import records

MECHANICAL = ("核对", "结论", "说明")
SECTIONS = ("段位", "结论")


@dataclass
class Result:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = field(default_factory=list)


def short(root: Path, path: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


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


def list_all(root: Path) -> Result:
    catalog = catalog_layer.build(root)
    result = Result(columns=("种类", "路径"))
    for entry in catalog.entries:
        rel = short(root, entry.path)
        result.lines.append(f"[{entry.kind}] {rel}")
        result.rows.append((entry.kind, rel))
    return result


def list_payload(root: Path) -> dict:
    catalog = catalog_layer.build(root)
    return {
        "root": root.name,
        "count": len(catalog.entries),
        "entries": [
            {"kind": entry.kind, "path": short(root, entry.path), "names": sorted(entry.names)} for entry in catalog.entries
        ],
    }


def check(root: Path) -> Result:
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    ok = not (missing or unregistered)
    result = Result(ok=ok, columns=("问题", "说明"), rows=[("缺资产", f"{a.kind}（{a.name}）") for a in missing] + [("未登记", short(root, p)) for p in unregistered])
    result.lines = [f"{kind}：{what}" for kind, what in result.rows]
    if ok:
        result.lines = ["对账通过：二十格齐备，无未登记目录。"]
    return result


def check_payload(root: Path) -> dict:
    missing = assets_layer.missing(root)
    unregistered = catalog_layer.build(root).unregistered(root)
    return {
        "root": root.name,
        "result": "通过" if not (missing or unregistered) else "有问题",
        "missing": [{"kind": asset.kind, "name": asset.name} for asset in missing],
        "unregistered": [short(root, path) for path in unregistered],
    }


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


def new_record(target: Path, template: str) -> Result:
    if not str(target).strip():
        return Result(ok=False, lines=["请先填写到哪个文件"])
    if target.exists():
        return Result(ok=False, lines=[f"已存在：{target}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    return Result(lines=[f"已写：{target}"])


def audit_contract(root: Path, target: Path) -> Result:
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
    return result


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
