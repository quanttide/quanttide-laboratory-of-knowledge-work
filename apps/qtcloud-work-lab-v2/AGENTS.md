# AGENTS —— 实验室工作纪律（v2）

本 app 是量潮知识工作实验室 v2（`qtcloud-work-lab-v2`），按规格重写、功能对表 v1。在这儿干活的 AI 与人都按本文办。

## 数据：账本归 CLI，内容归工作区

**CLI 自己维护的东西（账本）落 CLI 自己的数据目录，不写进任何工作区**：

```text
$XDG_DATA_HOME/qtcloud-work/            # 缺省 ~/.local/share/qtcloud-work
└── workspaces/<工作区键>/
    ├── workspace.yaml                 工作区身份：id / name / title / description / created_at / updated_at
    ├── workflows/<工作流>.yaml         定义：name、description 与 steps（每步 name / description / executor / criteria）
    ├── workorders/<工单>.yaml          工单：封面（id / name / description / workflow_id / created_at）加流水（records）
    ├── artifacts/<类别>/<工单名>.md     产物按类别分家，按工单名命名
    └── events.jsonl                   领域事件：WorkflowCreated / WorkOrderCreated / WorkRecorded，一条一行，只增不改
```

`<工作区键>` 由工作区根的路径派生（可读名 + 短码）——账本是「这台机器上的这个工作区」的账。

**工作区根是人自己的地方**：材料、定义、产物由人放；程序只在点了明确要写的动作时动它。定义要跟工作一起沉底（入版控、可分享），就 `--workflows` 另指一处固定资产目录（如 `data/profile/iGuo/workflows/`）；账本要入版控，就 `--data` 指到仓库。

## 单一事实源

本 app 的模型以规格为准：`docs/specification/process/` 的工作流、工作步骤、工单、工作记录四篇。规格没规定的操作不发明——v1 里规格之外的动作用「实验室自留」标记。

## 定义不带凭证

人写的定义（工作流、工作步骤）不写 `id`：凭证由工作区按「工作区 id + 名字」现算，所以一份定义指到哪都能直接跑。程序写的账本（工单、工作记录）照旧带凭证——它们是事实的实例。

## 定义一经引用即冻结

被工单引用的工作流不可改——改步骤、删步骤、调次序，另立新工作流。本程序不设改定义的口子（改就直接改 YAML，那句话不由程序说）。

## 禁止过滤

扫描时允许跳过的只有版本库与构建产物这类非数据目录——`.git/`、`.venv/`、`node_modules/`、`__pycache__/`、`build/`、`dist/`；除此之外一律不过滤。
