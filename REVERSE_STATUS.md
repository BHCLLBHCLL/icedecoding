# Icepak 项目文件/目录逆向解析 — 状态总结

> 生成时间: 2026-08-24
> 范围: 对 ANSYS Icepak (v19.5) 项目文件与目录的逆向解析实现现状

## 1. 项目目标

解析 ANSYS Icepak 的项目文件（目录结构 + `.tzr` 打包归档），还原其中的几何对象、求解设置、网格参数、材料与后处理对象，并支持 JSON / CSV 结构化导出与 3D 可视化预览。

## 2. 当前总体状态

**核心解析链路已跑通，全部 26 个项目扫描通过、无解析异常、无未知对象类型、post 引用对象全部可在 model 中找到。**

- 已解析项目数: **26**（17 个目录 + 9 个 `.tzr` 归档）
- 覆盖对象类型: domain / block / plate / source / fan / opening / wall / pcb / package / heatsink / material / part / resistance / ventres / enclosure / assembly 等
- 解析对象总数: 约 **1200+**（单项目最多 259 个，如 datacenter）
- 交叉验证: 全部项目 `post_missing_in_model = []`、`unknown_object_types = []`

## 3. 逆向解析方法论

编码算法并非文档公开，而是通过对 **icepak.exe 反汇编 + 统计分析** 逐步复现：

| 阶段 | 手段 | 产物 |
| --- | --- | --- |
| 二进制定位 | 在 icepak.exe 中搜索特征字符串/常量 | `search_exe.py` / `search_binaries.py` / `find_refs.py` |
| 反汇编 | 定位混淆编码相关函数并人工分析 | `disasm1/2/3.py`、`func_disasm.txt` |
| 编码分析 | 从反汇编还原 `v = c - KQ[i%7] - KC[i%16] - seed` 公式 | `decoder.py` 中公式注释 |
| 统计验证 | 位置频率分析、字符集分布、往返编码验证 | `analyze2.py` / `analyze3.py` / `analyze_encoding.py` / `test_decode.py` / `verify_full.py` |
| 归档格式 | 识别 `.tzr` 为 gzip+tar 双层封装 | `dump_bytes.py` / `tzr.py` |

### 3.1 混淆编码 (Il!!)

model、materials_from_libraries 等文件以 `Il!!` 开头并整体混淆：

- 解码: `v = c - KQ[i % 7] - KC[i % 16] - seed`，`v < 0x20` 时循环加 `0x5F`
- 密钥: `KQ = "q|sz}y~"`（周期 7）、`KC = "cor5(#b!S0efP3+E"`（周期 16）
- seed = `Il!!` 后的第一个字符；有效字符区间 `0x20–0x7E`，周期 lcm(7,16)=112
- 已实现可逆编解码（`decoder.py`），同 seed 往返一致

## 4. 已实现能力（icepak_parser 包）

| 模块 | 功能 | 状态 |
| --- | --- | --- |
| `decoder.py` | `Il!!` 混淆编解码（双周期密钥 + 行种子，周期 112） | 完成，155 行密文同 seed 往返 100% 还原 |
| `tzr.py` | `.tzr` gzip+tar 解包（含内存流式） | 完成，avonics.tzr → 5 个项目文件 |
| `model_parser.py` | model 文件 → 对象树（object/shape/setval/嵌套 assembly） | 完成，递归计数/几何提取正确 |
| `problem_parser.py` | problem 文件 → set / array set（含跨行 block） | 完成，408 set / 47 array，problem_ambient 21 项正确 |
| `project.py` | 目录/归档聚合入口 + main.ice.xml / grid_params / materials / post_objects | 完成 |
| `export.py` | 类型化导出 JSON / objects / problem / grid CSV，几何量提取（bbox/center/radius 等） | 完成，修复坐标含 0 的边界计算 bug |
| `cli.py` | 批量 scan + 交叉验证（post 引用、grid 对照、未知类型） | 完成，post 引用含嵌套 assembly 全部 resolve |
| `ice_gui.py` | PyQt5 + VTK 3D 可视化查看器：7 种 shape 几何构建（hexa/quad/cyl 含空心/polygon/circ/container/none）、15 类对象分图层渲染（Shading/Line/Translucent）、拾取联动/双击聚焦、headless 测试模式 | 已验证（几何 1195/1247 成功；headless 全流程通过；3D 渲染需桌面 GL 环境） |

## 5. 交叉验证结果（_report/report.json）

- post 对象引用的 model 对象名：**全部命中**（各项目 `post_missing_in_model` 均为空）
- 未知对象类型：**0 个**
- grid_params 行类型与 model 对象类型分布可对照（信息性校验）

## 5.1 GUI 验证（ice_gui.py）

- 几何管线：26 个项目共 **1247** 个对象，**1195** 个成功构建 3D 几何（其余 52 个为 shape_none 空对象/无几何，正常跳过）
- headless 测试模式（`enable_3d=False`）：目录扫描 → 树填充（对象分组/问题设置/文件列表）→ 对象选中 → 属性表 → tzr 归档载入 → 图层/渲染模式切换，全部通过
- 依赖：PyQt5、vtk 9.3.1、numpy 已就绪
- 说明：offscreen 无 GL 环境下 3D 渲染无法验证（VTK 需真实显卡上下文），属环境限制；3D 效果需在正常桌面会话中启动查看

## 5.2 关键问题修复

- `all()` 误判 0 坐标为假：坐标含 0 时包围盒计算被错误跳过，已修复边界计算
- 对象按名查找需递归进嵌套 assembly：`object_by_name` 已支持嵌套子对象递归查找，post 引用（含嵌套）全部 resolve

## 6. 已知限制与待办

| 项 | 说明 |
| --- | --- |
| 多 shape 对象 | `model_parser` 目前只保留最后一个 shape；`end shape` 嵌套时处理有缺陷 |
| 多边形几何 | `shape_polygon` 仅标注 "详见 setvals"，未提取顶点坐标 |
| 其他 shape 类型 | 仅 hexa/quad/plate/cyl 有几何提取，其余走通用 pts |
| grid_params | 仅 token 级切分，未结构化解释各字段含义 |
| problem 数组 | `_pairs` 只处理标量键值，列表/嵌套值未完整建模 |
| 硬编码路径 | 多个脚本默认参数硬编码 `D:\training\icepak` |
| GUI 3D 环境 | 3D 渲染需真实显卡上下文；offscreen/无 GL 环境仅可 headless 测试（`enable_3d=False`），属环境限制而非代码缺陷 |

## 7. 目录结构

```
icedecoding/
├── icepak_parser/         # 核心解析库
│   ├── decoder.py         # Il!! 混淆编解码（逆向自 exe）
│   ├── tzr.py             # .tzr 归档解包
│   ├── model_parser.py    # model 对象树解析
│   ├── problem_parser.py  # problem 设置解析
│   ├── project.py         # 聚合入口
│   ├── export.py          # JSON/CSV 导出
│   └── cli.py             # 批量扫描 + 交叉验证
├── ice_gui.py             # PyQt5+VTK 3D 查看器
├── disasm*.py / func_disasm.txt   # 逆向分析脚本与反汇编输出
├── analyze*.py            # 统计分析脚本
├── verify_full.py / test_decode.py # 解码验证
├── _report/               # 批量扫描报告（json/csv + 各项目导出）
└── _out/                  # 示例导出
```

## 8. 结论

三阶段开发规划已全部实施并验证通过：

- **阶段 1（核心解析库）**：Il!! 编解码、.tzr 解包、model/problem 解析、项目聚合 — 完成
- **阶段 2（数据模型与导出）**：几何量提取 + JSON/CSV 导出 + 项目汇总 — 完成
- **阶段 3（批量工具与验证）**：CLI 批量扫描 26 个项目 + 交叉验证（post 引用/未知类型）— 完成，零崩溃、零未知类型

逆向解析主线（混淆解码 → model/problem/网格/材料/后处理解析 → 聚合导出 → 可视化）已全部实现并通过 26 个真实项目验证。关键技术风险（Il!! 编码破解）已消除。后续工作重点是补齐多边形/多 shape 几何解析与 problem 数组结构化。

---

## 9. GUI 100% 对标进度（P0 完成 / 2026-08-25 起）

> 总规划：docs/ICEPAK_UI_100PCT_PLAN.md（P0->P9）；每次关键功能提交同步更新本节。

### P0 — 黄金规格驱动命令注册表（完成）

- 新增 ice_actions.py：CommandRegistry（加载 docs/icepak_gui_golden.json：11 菜单全树 / 9 工具栏 / 79 热键 / 70 图标键 / File 双变体），命令到槽位解析（SLOT_MAP + resolve_slot），图标键到矢量图标别名（ICON_ALIASES/icon_for_command），NYI 通道（NyiHandler -> Message WARN 红色）。
- 新增 ice_menus_toolbars.py：由 golden 生成 QMenuBar（级联/分隔/热键语义）、9 组三行工具栏（row1 file/edit/viewing/orientation，row2 model+post，row3 object_tools）、窗口级热键（Ctrl-N/O/S/Z/R/F/E/X/C、Delete、Ctrl-A/V/T/M/W/L 等）；特殊控件（Default shading 单选组、Object names 单选组、Visible 逐类型复选、Edit toolbars 复选菜单、User views/Windows/Macros 动态菜单）保留专用构造器。
- 改造 ice_gui.py：_build_menus/_build_toolbars 改为 registry 驱动（菜单硬编码清单清除）；状态项（Display mesh/Visible grid/...）落 _display_state；_created_by_command 供热键/测试寻址。
- 改造 ice_panes.py：MessageWindow 按级别着色（WARN/ERROR 红，INFO 黑，DEBUG 灰）——对齐原版 mess <text> <color>。
- 新增 tests/test_golden_ui.py（8 项）：注册表/菜单树=golden/命令全覆盖/工具栏组=golden/图标/热键/NYI 落消息/状态开关。
- 回归：原 27 项测试 + 新 8 项 = 35 项全绿（headless offscreen）。
- golden 生成工具：tools/gen_golden_spec.py（可重跑校验）、tools/pe_strings.py、tools/parse_commands.py、tools/icon_lookup.py、tools/commands_registry.json（301 命令注册表）。

### 下一步（P1 -> P4）

P1 壳层：右下当前所选对象几何信息窗口、项目标题条、Welcome 流补齐、New Project 面板、Edit toolbars 行为、Windows 动态菜单；P2 树与导航；P3 3D 完整化；P4 Form 引擎 + 18 类对象编辑器。
 + JSON.stringify(addition) +  + JSON.stringify(addition) +  + JSON.stringify(addition) +  + JSON.stringify(addition) + 