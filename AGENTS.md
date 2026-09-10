# AGENTS —— 实验室工作纪律

本仓是量潮知识工作实验室（`quanttide-laboratory-of-knowledge-work`）。在这儿干活的 AI 与人都按本文办。

## 数据：全部放 `data/`

**所有数据放本仓的 `data/` 下，不许写到实验室外面**——工作区的 `data/`、规格、手册、案例都算外面。

```text
data/
├── workflows/<工作流>.yaml      工作流：串联的步骤（name / what / executor / judges）
├── tasks/<任务>.yaml            任务：工作流的一次执行（workflow、goal）
└── artifacts/<任务>/
    ├── log.jsonl              执行记录
    ├── report.md              报告（事件）：执行记录 + 闸门项
    └── history.md             历史（叙事）
```

目录按领域模型分三家：workflows（过程的编排定义）、tasks（工作流的一次执行实例）、artifacts（产物）。

**定义用 YAML，记录用 Markdown**：工作流与任务要「意义固定」（字段、取值由 schema 定死），所以是 YAML；报告与历史是读物与叙事，仍是 Markdown；流水是 JSONL。

**判据按主体分三类，取值英文标识**：`rule`（规则引擎跑 spec）、`agent`（智能体照判准审）、`human`（留给人）；执行者 `executor: agent|human`。不认识的字段直接报错，不许默默忽略。

程序默认就写在这里（`kg --data`，缺省即本仓 `data/`）；要写别处必须显式指路。

## 禁止过滤

**数据全量落位，不挑拣、不跳过、不丢弃、不留副本了事。**

扫描时允许跳过的只有版本库与构建产物这类非数据目录——`.git/`、`.venv/`、`node_modules/`、`__pycache__/`、`build/`、`dist/`；除此之外一律不过滤。这条豁免在代码里写死并写明（`src/kg/catalog.py` 的 `SKIP`），不许悄悄多滤，也不许把过滤藏在别处。

## 边界

- 只在实验室内做；实验阶段产物不得溢出到工作区的 `data/*`、规格、手册、案例；
- 数据是产物不是代码：进来的东西放上面的格子，不塞进 `src/` 或 `docs/`；
- 数据改动也要提交：与代码同仓，一起进版本库。
