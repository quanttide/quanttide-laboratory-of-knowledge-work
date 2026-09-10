# 过程

过程分两侧（`specification/process/`）：**工作流**是过程的编排定义，**任务**是过程的一次执行。一句话记住：**先串步骤，再执行**——工作流是可改、可复用的数据，任务是一次执行。

## 一、写工作流（可改）

```bash
$ kg workflow --new 课程档案比对 --steps 定位,比对,结论 --note "比对两边的档案"
写下工作流：…/data/workflows/课程档案比对.md
```

落在 `data/workflows/<名字>.md`，步骤用 `### 步骤名` 串，**每步自带验收**：

```markdown
# 工作流：课程档案比对

## 步骤

### 定位

- 做什么：把两边的源找齐
- [ ] 机械：个人课程档案在 `path:data/profile/iGuo/course/index.md`
- [ ] 机械：课程研发档案在 `path:/home/iguo/repos/quanttide/domains/quanttide-course/data/profile/README.md`

### 比对

- 做什么：逐项对照，落成一件产物
- [ ] 机械：产物落成 `path:examples/default/data/artifacts/课程档案比对/比对.md`
- [ ] 机械：产物点到两边的课 `contains:…比对.md=production-internship`
- [ ] 闸门：创始人点头（回流与并法怎么定）
```

判据四种、路径相对工作区根（写绝对路径则按绝对路径，跨仓库核对用）：`` `path:` `` 存在、`` `absent:` `` 不存在、`` `contains:文件=文字` `` 含某段文字、`` `run:命令` `` 退出码为零。没有判据的条目是**闸门项**，列给人拍板。

**可改**就在这儿：加一步、去一步、换顺序、改判据——动这份 Markdown 就行，程序一行不用改；进 git 能 diff、能回退。

```bash
$ kg workflow 课程档案比对      # 看步骤与各步几条判据
$ kg workflow --list           # 有哪些工作流
```

## 二、起一件任务（复用）

```bash
$ kg task --new 课程档案比对 --workflow 课程档案比对 --about "比对 work 侧与课程研发档案"
起了：…/data/tasks/课程档案比对.md
```

**同一条工作流可以起任意多件任务**：任务＝它的一次执行，各自有步骤状态、流水与产物，互不串。工作流文件拷到别的 `--data`，整套做法就跟着过去。

（注意：现在任务按名字引用工作流，**中途改工作流等于改了正在跑的任务的规矩**。要锁住当时的样子，把工作流快照一份到 `artifacts/<任务>/`。）

## 三、走一步

```bash
$ kg task 课程档案比对 --done 定位 --note "work 侧 3 件、course 侧 3 门课"
✓ 定位：work 侧 3 件、course 侧 3 门课
  ✓ 机械：个人课程档案在（path:data/profile/iGuo/course/index.md）
  ✓ 机械：课程研发档案在（path:/…/course/data/profile/README.md）
下一步：比对
```

`--done <步骤>` 做三件事：跑这一步的机械判据、记一笔流水、刷新报告。没有判据的步骤也能记一笔（`--note` 一句话）。

## 四、看

```bash
$ kg task 课程档案比对
  ✓ 定位   ✓ 比对   ✓ 结论
3 个步骤都走过了
产物：artifacts/课程档案比对/report.md、artifacts/课程档案比对/history.md

$ cat data/artifacts/课程档案比对/report.md     # 执行记录 + 闸门项，机器写
```

## 五、收尾

闸门项留给人拍板；这一趟的来龙去脉写进历史（叙事，人写）：

```bash
$ kg task 课程档案比对 --history "先找齐两边，再按口径 / 重叠 / 缺口 / 格式差四条比……"
```

## 数据：三家分放

```text
data/workflows/<工作流>.md     定义：串联的步骤与判据
data/tasks/<任务>.md           实例：跑哪条工作流、要什么
data/artifacts/<任务>/         产物：log.jsonl、report.md、history.md
```

## 窗口里也一样

`./kg-gui` 台面：上方选一件任务、可以新建；中间是步骤表（步骤 / 怎么算完 / 状态）；填一句「这一步做了什么」，点「走这一步」；「看工作流」打开定义，「写历史…」记叙事。

## 规矩

- **数据全落 `data/`**（workflows / tasks / artifacts 三家），不写实验室外面；
- **判据写进步骤的验收**，模板里的占位（`<…>`）不算判据；
- **工作流是数据不是代码**：改流程不改程序；程序不预置编排，也不替你攒模板——想留，自己把文件放过去；
- **别人的仓库不擅动**：跨仓库的动作（如 course 侧）要授权。

## 真事一例

2026-09-10 那次比对（就是上面这份）：

```bash
kg workflow --new 课程档案比对 --steps 定位,比对,结论
kg task --new 课程档案比对 --workflow 课程档案比对 --about "比对两侧课程档案"
kg task 课程档案比对 --done 定位 --note "work 侧 3 件、course 侧 3 门课"
kg task 课程档案比对 --done 比对 --note "口径 / 重叠 / 缺口 / 格式差"
kg task 课程档案比对 --done 结论 --note "四条处置建议，闸门待创始人"
```

比出来的四条：口径不同（一边记「为什么这么办」，一边记「课里有什么」）；production-internship 两边都有却互不引用；各有缺口（work 侧有「知识工作」课与验证目标，course 侧有 vibe-coding、data-engineering 与格式约定）；格式差最要命——course 侧机读、work 侧散文，对不了账。结论挂在闸门上等创始人。
