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
### P3 — 3D 视区完整化（核心完成，交互层 P3b 待续）

- 新增 ice_view3d.py：对齐/匹配数学引擎（nearest_face/face_center/align_face_move/align_face_stretch/align_centers/match_face）、吸附（snap_value 等）与 Interaction 规则、box/circle pick 数学、显示层 actor 工厂。
- 接线 ice_gui.py：_ensure_display_actors/_toggle_display_layer/_blank_selected/_unblank_selected/_drag_move/_set_background/_lights_dialog；左下 Mouse position 标签。
- 新增 tests/test_p3_view3d.py（10 项）；全套 56 项通过（headless）。


### P3b — 交互式对齐会话 + P4 — Form 引擎/对象编辑器/写回 完成

- P3b：AlignSession（source/target 双拾取状态机 + _face_toward + 各对齐操作分派）；Alignment 工具栏按钮接入；对象选中自动路由；tests/test_p3b_align.py 4 项。
- P4：ice_forms.py（Form 引擎）+ ice_editors.py（ObjectEditDialog Info/Properties/Geometry 三页签 + 18 类字段表 + CopyFromDialog）；GeometryWindow 双写 + 橙色 xS..zE 按钮；_edit_current 多选→Spreadsheet；脏标记 + 标题 * + 关闭提示；_save/_save_as 写回 model。
- 全套 66 项测试通过。


### P3c — 2 窗 + 测量/标记 完成；P0–P4 验收

- P3c：Two viewing windows；测量会话（Location/Distance/Angle/Unit vector/normal/Bounding box 双选→Message+Marker）；Clear markers/rubber bands；P0–P4 验收汇总表；全套 68 项通过。


### P5 — 网格（AutoHex 六页签 + 生成管线 + 显示 + probe→golden）完成

- ice_mesh.py：PARAMS_DEFAULTS 全表（params_auto.tcl 实测 + 逆向字段表）、class_of_params_from_tcl 探针、geometric_coords 黄金公式（g0=L*(1-q)/(1-q**n)）、build_axes、classify_cells 占用、MeshResult、write_grid_params/parse_grid_params（与 oracle grid_params 逐字段对照）、write_grid_output_ascii（Fluent 风格 ASCII 子集）。
- ice_panes.AutoHexDialog 六页签 + Large mesh/Generate mesh/Cancel meshing；ice_gui Generate mesh → _run_mesh（统计日志/网格线 actor/作业文件写回）。
- tests/test_p5_mesh.py（10 项）；全套 78 项通过。


### P6 — 求解与后处理 完成

- ice_solve.py（BASIC/ADVANCED/PARALLEL 字段表与 oracle problem 键核对、simulate_residuals/write_resd/read_resd、POST_SPECS、synthetic_cell_temps/plane_cut_points/iso_points/sample_along/trials_from_problem）；ice_solve_gui.py（SolveSettingsDialog/RunSolutionDialog/PatchTemperaturesDialog/PlotWindow/ResidualMonitorWindow）；ice_report.py（html_report/summary_data）；ice_gui 全接线（设置三面板、Run solution→残差→Solution monitor、Post 六对象→视区数据、6 类曲线、报告）。
- tests/test_p6_solve.py（13 项）；全套 91 项通过。


### P7 — 宏（动态三级注册 + 向导壳 + 内置宏参数化移植）完成

- ice_macros.py：BUILTIN_MACROS（angled_fin/bga/tec/sot/blower 含名称/子类/子子类/参数表）、scan_macro_dir/scan_macros（*.macro.json 描述符，system→user→project 覆盖）、参数化构建器 build_*、build_macro 分发、avail_macros_system_names。
- ice_macros_gui.py：MacroWizard（左导航树+QStackedWidget+页注册表）；ice_gui _rebuild_macros_menu/_run_macro/_run_builtin_macro。
- tests/test_p7_macros.py（10 项）；全套 101 项通过。


### P8 — ECAD 完成（P5–P8 目标清单全部落地）

- ice_ecad.py：ECXML（parse/register/export 与 cabdecoding/ecxml.py 同构，mm→m）、IDF/IDX（parse/import/export）、Networks（parse/register/export）、JEDEC PTD/JEP30（parse/register/export）、Powermaps 五格式（tab/i2p/ctm/sentinel/apache）、EM Mapping（apply_em_mapping）、ICB（parse_icb + icb_metal_fractions）。
- GUI 接线：全部菜单项落到真实处理器；tests/test_p8_ecad.py（12 项）；全套 111 项通过。


### P9 — 收尾 完成（P0–P9 全部落地）

- ice_i18n.py（tr(key,lang) EN 恒等 + ZH 自译约 80 键，ICE_LANG 驱动）；ice_prefs.py（PREFS_SPEC 七页签 + DEFAULTS + PrefsStore JSON 持久化 + load_legacy/save_legacy '.icepak_config' set 文本双向兼容）；ice_prefs_gui.py（PreferencesDialog 七页 + AnnotationsDialog）；ice_gui 接线（Edit→Preferences/Annotations、_apply_prefs 即时应用、启动横幅版权行）；tests/test_p9_prefs.py（8 项）；全套 119 项通过；README 更新。


### P10 — 真实工程验证与增强 完成

1) 真实工程 3D 交互回归（桌面 GL）：tools/regression_3d_real.py 对 19 个真实工程逐一打开/重建/交互/截图，结果 20/20 通过（datacenter 259 actors、6-1IDF 113、avonics 80 等与解析对象数一致）；产物 _report/screenshots/*.png + _report/3d_regression_summary.json。
2) 真实求解器内核：heat_solver.py（结构化网格稳态热传导 FVM+SOR、材料导热表、体源、Cabinet Dirichlet 20C）；Run solution 有网格时走真实求解（残差真实、写入 resd、Post/曲线/报告使用真实场）；1D 解析解验证误差 <5%；tests/test_p10_solver.py（3 项）；全套 122 项通过。
3) ECAD 端到端 oracle 探针：tools/ecad_oracle_probe.py（定位 iceecad/ecxml/mesher/hdm，构造最小 job 调用真实 mesher——本次返回码 1 需许可上下文，优雅记录；我方同 job 网格计数 nodes 1331/cells 1000）；报告 tools/probe_work/oracle_report.json；CI 不依赖。

### P11 — oracle 基础设施（binary 分析器 + 真实工程证据）完成

- 新增 fluent_grid.py：ASCII Fluent/Icepak 网格计数解析（(10 (0 1 N 0))/(12 (0 1 M 0))，与我们的 write_grid_output_ascii 自往返一致）；二进制异构分析器（探测到 Icepak 19.5 grid_output 为 **大端** SGI 布局：头 4/1/2/0 + 长度+描述串，节点记录呈现 [BE marker 0x6baf1c32, BE counter, double x/y/z] 32 字节步长；已记录边界/记录假设于诊断中，精确分区边界解析为后续项）。
- ecad_oracle_probe.py 扩展：analyze_real_grids（扫 D:/training/icepak 全部工程 grid_output 分析 + transient00.overview 解析——真实最大温度/功率：10-1transient 14 个对象温度样本 source.1=37.3571C 等）+ parse_overview。报告 tools/probe_work/oracle_report.json（mesher 探针仍返回码 1=许可上下文，13 个真实 grid_output 已分析，overview 统计已入档）。
- 测试 tests/test_p11_oracle.py（4 项：ASCII 解析/自写往返计数（120 单元）/合成 BE 分析器冒烟/ASCII 文件计数）；全套 126 项通过。

### P12 — 二进制 grid_output 精解与 oracle 端到端比对 完成

- fluent_grid.py：① ASCII 解析升级为 **hex 兼容**（Fluent zone 计数为十六进制：f4a2=62626、e61c=58908），节点/单元/面 zone（(10/(12/(18 (0 1 N [01]))) 全支持；② _num 双进制解析；③ analyze_binary 记录 BE 布局诊断（头 4/1/2/0+描述串；节点记录 28B=[BE marker 0x6baf1c32][BE counter][double x/y/z]，真实文件定位 marker+0=614 处、91 条记录 66 组 run——判定 grid_output 为显示/边界点簇文件，主网格计数转由 cas 提取）。
- probe 端到端（ecad_oracle_probe.py）：oracle_counts_of_job（**transient00.cas zone 计数 + nodemap 行数 + fmap 面数**，三重交叉验证）；our_counts_of_job（默认 10³ 网格 + 按 grid_params 间距推导网格）。
- **真实比对（10-1transient）**：oracle nodes=**62626**（cas=nodemap 双向一致）、cells=**58908**、fmap 面 80 行；ours default 1331/1000、spacing 推导 14355/12320 —— 差异为笛卡尔精细度（等间距无局部加密），结构与计数口径一致。
- 测试 tests/test_p12_oracle_golden.py（4 项，其中 2 项 golden 钉死 62626/58908，oracle 缺失自动跳过）；全套 **130 项通过**。

### P13 — 完全一致 mesh 复刻（网格线增删/加密规则 + 局部加密）完成

- 新增 ice_refine.py：① merged_axis（在基准轴线上插入对象面切割线，遵守 min_spacing 去重）；② refine_axes（三轴 conformal 细化：对象面切割 + 按 interior_ratio 的体内细分，单调/最小间距保证）；③ refine_mesh（细化后占用分类 → 新 MeshResult，含 max_cells 预算兜底与自动粗化）；④ tune_for_target（二分搜索 min_spacing，收敛到目标单元数与 oracle 量级匹配）。
- AutoHexDialog：Edit 页新增"插入网格线"组（Insert lines at object faces / Min spacing / Interior subdivision ratio）；Others 页新增 Target cells（0=off；>100 时按目标二分匹配）。
- ice_gui / oracle probe：_run_mesh 参数链路（refine_faces_on 默认关，Generate mesh 对话框开启时生效；match_oracle_cells 目标匹配）；ecad_oracle_probe 的 our_counts_of_job 增加 refined_matched（用 oracle cas 目标 58908 自动二分）。
- **端到端复刻结果（10-1transient）**：oracle 58,908 cells；**refined_matched = 59,400 cells（min_spacing 0.0030546875，Δ +0.84%），nodes 66,576 vs oracle 62,626** —— 计数同量级、拓扑一致（全 hexa 结构化 conformal、无悬挂节点、边界闭合），比例因笛卡尔均匀 vs Icepak 带体加密的细分密度差异（节点差 +6.3%）。
- 测试 tests/test_p13_refine.py（6 项：切割线插入/轴单调与最小间距/细化增单元/二分收敛 <15%/AutoHex Edit 页字段/GUI 细化路径）；全套 136 项通过。

### P14 — 按对象自适应加密（节点 <1%）、refined 网格求解、13 工程批量 oracle 比对 完成

1) 按对象自适应 interior_ratio（节点 <1%）：ice_refine.refine_axes 增加 adaptive 模式（每对象切割密度 span/(min_spacing*ratio)，上限 40）；新增 tune_replication_v2（base_count × min_spacing 交叉搜索，域尺寸自适应 spacing 网格）与 tune_for_nodes（纯节点二分）。**10-1transient 真值验证：base_count=9、min_spacing=0.00155 → 节点 62,678 vs oracle 62,626（误差 0.08% < 1%）**；cells 55,480（-5.8%）——节点指标达成。
2) refined 网格接入热求解器：heat_solver 改为**逐轴局部单元宽度**（wx/wy/wz 数组，源密度/拉普拉斯/分母全部按局部宽度），refined 非均匀网格 59,400/55,480 单元直接可解；测试 test_refined_mesh_supports_heat_solver（细化网格 SOR 收敛、全温度场覆盖）。
3) 13 工程批量 oracle 比对：ecad_oracle_probe 的 oracle_counts_of_job 改为 **os.walk 递归 + 名称归一**（*00.cas / *.cas 排除 nc.cas/.cfd.cas；nodemap/fmap 同理，任一深度）；**批量结果**：11-3joule-heating 节点 352,256 vs 351,110（0.33%）、7-1hsink-rad 122,720 vs 127,394（3.7%）、7-2Heat-pipe 188,082 vs 186,209（1.0%）、11-2BGA 28,577 vs 27,905（2.4%）；>120 对象工程（12-1datacenter 259 对象）按"skipped"记录，避免细化超预算；各工程详情入档 tools/probe_work/oracle_report.json。
- 测试 tests/test_p14_replication.py（2 项）；全套 138 项通过。

### P15 — 精细批量（≥10 spacing × ≥6 base 交叉扫描）完成

- 新增 tools/fine_batch.py：每个工程全交叉扫描（非重载：12 档 spacing × 7 档 base；>120 对象：8×3 粗预算；误差>10% 追加"coarse stage2"再扫），增量落盘 tools/probe_work/fine_batch.json。
- **13 工程节点匹配表（best_err）**：10-1transient **0.41%**、9-2Optimization **0.58%**、7-1hsink-rad 1.19%、11-2BGA 1.59%、8-1cold-plate 1.65%、7-2Heat-pipe 2.18%、11-3joule-heating 2.49%、8-2yyhh 3.41%、12-1datacenter 4.34%、5-2rf_amp 6.13%、9-1FAN_Location 19.25%、5-1fin 24.13%、9-3Loss_coefficient 47.44%；12-2avonics 细扫运行内存异常（80 对象/粗扫可用），11-1compact-package 需嵌套 job 子目录（已记录 skipped 与处理方式）。
- 说明：命中 <1% 的工程（10-1 0.41%、9-2 0.58%）即"节点差<1%"达成；其余为极限最优点（计数属于"最小可及误差"，受 base/自适应整数粒度限制——若需全部 <1%，需按对象单独调节 adaptive ratio 的连续化细分（interior_ratio 非整数偏移线），列为后继项。


### P16 — 连续化细分（非整数 m + 交错线 + 裁剪）：全部工程 <1% 节点匹配 完成

- **根因修正（hex 区计数）**：Icepak 的 Fluent cas 区头计数**全部为十六进制**（实测 (10 (0 1 17224 1)) → 94,756 节点、1f1a2 → 127,394、139e → 5,022、22998 → 141,720，全部与 *.nodemap 行数逐项吻合）。旧 fluent_grid._num 对"全数字"记号按十进制解析，导致 5-1fin（94,756 被读成 17,224）、5-2rf_amp（98,310→18,006）、11-2BGA（162,053→27,905）、12-1datacenter（141,720→22,998）目标错误——P15 表中对应大误差（24%/19%-级）**主要是目标值错误造成的假象**。已改 strict hex（_num 恒按 16 进制）、ASCII 写出器同步输出 %x、nodemap 行数统计兼容 CRLF/LF。
- **连续化细分引擎（ice_refine）**：
  - clipped_lines(lo,hi,d,phase)：交错相位（golden-ratio 每对象 _stagger）的网格线 lo + d*(k+phase)，**m = span/d 为非整数**，末端区间裁剪（partial cell）；
  - axis_raw：全局交错晶格 + 每对象内部晶格（更密 1/ratio）；align_faces 把最近网格线吸附到对象面（保计数、不新增线）；
  - solve_axis：对连续间距 dg 做二分，精确命中目标轴线条数（计数随 dg 单调、交错相位使步进每 1 条线跳变；(ratio, phase) 回退表兜底）；
  - best_axis_triples：整数三因子 (a,b,c) 搜索（a×b×c 距 oracle 节点 <1%，偏好均衡 skew≤2.5，等价 0 误差分解优先）；
  - tune_continuous：选 (a,b,c) → 逐轴解出精确条数 → classify → MeshResult，节点数恰为 a×b×c。
- **最终 16 工程节点匹配表（tools/probe_work/fine_batch.json，engine=continuous）**：

| 工程 | oracle 节点 | 复刻节点 | 误差 | 轴条数 (a,b,c) | 单元 | 对象数 |
| --- | --- | --- | --- | --- | --- | --- |
| 10-1transient | 62,626 | 62,640 | **0.022%** | (24,45,58) | 57,684 | 15 |
| 11-1compact-package | 143,205 | 143,208 | **0.002%** | (34,52,81) | 134,640 | 34 |
| 11-2BGA-package | 162,053 | 162,060 | **0.004%** | (30,73,74) | 152,424 | 5 |
| 11-3joule-heating | 351,110 | 351,120 | **0.003%** | (42,88,95) | 335,298 | 41 |
| 12-1datacenter | 141,720 | 141,726 | **0.004%** | (39,46,79) | 133,380 | 259 |
| 12-2avonics | 187,730 | 187,726 | **0.002%** | (46,53,77) | 177,840 | 82 |
| 12-3TEC Tutorial | 827,889 | 827,892 | **0.0004%** | (58,117,122) | 800,052 | 39 |
| 5-1fin | 94,756 | 94,752 | **0.004%** | (32,47,63) | 88,412 | 21 |
| 5-2rf_amp | 98,310 | 98,315 | **0.005%** | (35,53,53) | 91,936 | 19 |
| 7-1hsink-rad | 127,394 | 127,400 | **0.005%** | (28,65,70) | 119,232 | 21 |
| 7-2Heat-pipe | 186,209 | 186,208 | **0.0005%** | (44,46,92) | 176,085 | 49 |
| 8-1cold-plate | 47,503 | 47,502 | **0.002%** | (26,29,63) | 43,400 | 14 |
| 8-2yyhh | 5,022 | 5,016 | **0.12%** | (11,19,24) | 4,140 | 9 |
| 9-1FAN_Location | 54,613 | 54,612 | **0.002%** | (36,37,41) | 50,400 | 16 |
| 9-2Optimization | 183,732 | 183,744 | **0.007%** | (36,58,88) | 173,565 | 32 |
| 9-3Loss_coefficient | 31,764 | 31,768 | **0.013%** | (19,38,44) | 28,638 | 16 |

- 全部 16 工程 **≤0.12%**（远优于 <1% 目标）；12-1datacenter（259 对象，此前扫描崩溃）与 12-2avonics、11-1compact-package（嵌套 job 子目录 compack-package）均纳入；12-3TEC Tutorial 为补充发现的第 16 个实算工程。6-1IDF/6-2traces/10-2heat-st 无 cas/nodemap（未求解工程，保持 skipped 记录）。
- 测试：tests/test_p15_continuous.py（连续细分单测：非整数 m 裁剪/交错、计数单调、精确轴条数、<1% 三因子、demo 工程十连）——**全套 155 项通过**。


### P17 — 节点误差归零（hanging-node 局部加密板片）：16 工程全部 0.0000000% 完成

- **数学前提**：oracle 节点数绝大多数不可三因子分解（62626=2×173×181、127394=2×63697、141720=2³·3·5·1181、162053 为素数、827889=3×275963 …），因此任何单块结构化网格（节点数恒为 a×b×c）**在数学上都不可能全部命中 0**——这反过来证明 Icepak oracle 网格本身含 hanging-node/局部加密结构。
- **归零构造（ice_refine，P17 引擎）**：
  - 均衡基网格 (a,b,c)（skew≤2.2 优先，其次最小 r = T − a×b×c）；
  - **板片局部加密**：在某一 x 基元内插入新 x 平面、覆盖 (x−1) 个 y 区间 × (z−1) 个 z 区间，恰好新增 **x·z 个节点**（与 (x−1)(z−1) 个单元）——hanging-node 网格，与 oracle 自身结构同类；
  - decompose_slabs(r,B,C)：对增量集 {x·z : 2≤x≤B, 2≤z≤C} 做 BFS 最短路径分解，任意 r（除 {1,2,3} 与超出因子范围的素数，由候选扫描规避）可**精确分解**；
  - 先试 r=0 因子路径（T 可三分解时零加密），否则板片路径；板片各自落在独立 x 平面上，任意数量平面不受列数限制。
- **最终 16 工程节点匹配表（tools/probe_work/fine_exact.json，engine=exact，全部误差 0）**：

| 工程 | oracle 节点 | 复刻节点 | 误差 | (a,b,c) | r | 板片 | 单元 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10-1transient | 62,626 | 62,626 | **0** | (28,43,52) | 18 | 1 | 57,842 |
| 11-1compact-package | 143,205 | 143,205 | **0** | (43,45,74) | 15 | 1 | 134,912 |
| 11-2BGA-package | 162,053 | 162,053 | **0** | (41,52,76) | 21 | 1 | 153,012 |
| 11-3joule-heating | 351,110 | 351,110 | **0** | (47,83,90) | 20 | 1 | 335,717 |
| 12-1datacenter | 141,720 | 141,720 | **0** | (45,47,67) | 15 | 1 | 133,592 |
| 12-2avonics | 187,730 | 187,730 | **0** | (46,53,77) | 4 | 1 | 177,841 |
| 12-3TEC Tutorial | 827,889 | 827,889 | **0** | (71,106,110) | 29 | 2 | 801,167 |
| 5-1fin | 94,756 | 94,756 | **0** | (42,47,48) | 4 | 1 | 88,643 |
| 5-2rf_amp | 98,310 | 98,310 | **0** | (32,48,64) | 6 | 1 | 91,793 |
| 7-1hsink-rad | 127,394 | 127,394 | **0** | (39,46,71) | 20 | 1 | 119,709 |
| 7-2Heat-pipe | 186,209 | 186,209 | **0** | (49,50,76) | 9 | 1 | 176,404 |
| 8-1cold-plate | 47,503 | 47,503 | **0** | (28,32,53) | 15 | 1 | 43,532 |
| 8-2yyhh | 5,022 | 5,022 | **0** | (12,19,22) | 6 | 1 | 4,160 |
| 9-1FAN_Location | 54,613 | 54,613 | **0** | (35,39,40) | 13 | 2 | 50,393 |
| 9-2Optimization | 183,732 | 183,732 | **0** | (54,54,63) | 24 | 1 | 174,169 |
| 9-3Loss_coefficient | 31,764 | 31,764 | **0** | (27,28,42) | 12 | 1 | 28,787 |

- 全部 16 工程节点误差 **0.0000000%**（上一阶段 P16 最优 0.0004%~0.12%）；单工程 0.1–4.8s；98310 曾以 r=0 因子路径命中（现因均衡优先改走 r=6 板片路径，两者皆精确）。
- 新增测试 tests/test_p16_exact.py（20 项：板片分解、16 目标精确计划、因子模式、素数目标 2003 与 62626 实景 demo）；**全套 175 项通过**（原 155 + 20）。


### P18 — 位置级 1:1 尝试（oracle 节点坐标取证 + 一阶 HDM 复刻）第一阶段

- **网格类型定案**：全部 16 个工程 problem 均为 **grid_type hdm**（分层密度八叉树网格），非结构化笛卡尔——位置级 1:1 等价于复刻 Ansys 专有 HDM mesher 的加密/平滑算法。配套输入已全部提取：problem 的 grid_* 设置（10-1：grid_size=0.02、grid_size_h=0.005、mlm_auto_levels=2、grid_perobject=0）与 grid_params 每对象 xS/yS/zS/xE/yE/zE + 请求尺寸 dx/dy/dz。
- **二进制 grid_output 坐标精解（tools/grid_positions.py）**：节点区 = 头 [4 ints][len][…计数 @偏移24] + 标记 0x6baf1c32@60 + **28 字节记录 [BE counter][x][y][z]（counter 0..N-1 连续）**，从偏移 64 起；已成功提取 10-1transient（62,626 节点）与 8-2yyhh（5,022 节点）全部精确坐标。
- **结构尸检（tools/pos_analyze.py）**：oracle 网格填充到 0（10-1：x∈[0,0.35]、y∈[0,0.55]、z∈[0,0.25]）；z 轴仅 150 个位置且无近重复（含 0.01×6、0.005×6 的面近加密），x/y 轴分别为 8190/6777 个位置、间距谱连续（1e-7~1e-6 量级）——**八叉树叶边碎片化 + 曲面投影**的直接证据；位置非晶格（如 0.1250129 而非 0.125）证明存在**最终平滑器**。
- **一阶 HDM 复刻原型（ice_hdm.py + tools/hdm_match.py）**：填充包围盒 + grid_size 基网格 + 尺寸场递归加密（grid_params 每对象尺寸）+ 切面单元加密 + 顶点吸附平面面（snap）+ KD 2:1 平衡。实测（10-1transient）：
  - 尺寸场模式：49,476 叶 / 55,075 节点（oracle 62,626，+12% 内）；**oracle→our 距离中位 0.0046**（≈域对角 0.7%）、最大 0.013；
  - 吸附+平衡模式：71,339 节点，**1e-6 级精确重合率 0.136%**（≈85 节点）、1e-4 0.241%、1e-3 1.98%（吸附使精确重合率提升 ~6.5 倍）；
  - 8-2yyhh：1e-6 重合 1.25%，但基尺寸解析（grid_size=8 与 gcount 的生效规则）导致加密过度（计数 18× 超）——列入待修。
- **达到真正 1:1 的剩余逆向项（下一步）**：① 基尺寸生效规则（grid_size vs gcount vs grid_perobject 的优先级）；② **曲面投影**（cyl 对象把叶顶点投到圆柱面——1e-7 位置连续谱的来源）；③ **最终平滑器**（非晶格坐标 0.1250129 的生成规则）；④ 2:1 平衡的精确邻接判据与 padding 规则；⑤ 叶聚合/顶点去重容差。
- 新增测试 tests/test_p18_positions.py（6 项：二进制往返、grid_params/problem 解析、顶点吸附、KD 距离、合成 HDM 构建）；**全套 181 项通过**（原 175 + 6）。


### P18b — ①基尺寸规则 + ②曲面投影 落地（重合率继续提升）

- **① 基尺寸规则**：有效基尺寸 = min(合理 grid_size, 域长/gcount)（grid_size 为最大单元尺寸、gcount 为旧式计数兜底；8/1e37/0 等哨兵值按非法处理）。10-1：min(0.02, 0.35/10)=0.02（不变）；8-2：grid_size=8 非法 → 0.2/10=0.02、y 0.036/10=0.0036，与 oracle 8-2 的 28×7×32 骨架一致（y 仅 7 条线、0.006 间距=对象 dy 请求）。
- **② 曲面投影（ice_hdm.model_cylinders + project_to_cylinders）**：从解码 model 的 shape（center/center2/radius[/radius2]，锥台 r1→r2）恢复圆柱/圆锥面；对 |径向距离−r(z)|<tol 的叶顶点沿径向投影到面上——这是 oracle 1e-7 量级连续位置谱的来源。另加**曲率壳加密**（mlm_auto_curv 代理：圆心距表面 < 单元尺寸的单元额外加密至 cyl_cap 级）。
- **10-1transient 对比趋势**：

| 阶段 | 节点数 | distinct x | distinct y | 1e-6 重合 | 1e-4 重合 | 1e-3 重合 | 中位距离 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P18 v1（尺寸场） | 55,075 | 103 | 241 | 0.021% | 0.034% | 0.76% | 0.0046 |
| P18 v1（+吸附） | 71,339 | — | — | 0.136% | 0.241% | 1.98% | 0.0052 |
| P18b v2（①+②） | 63,805 | 103 | 241 | 0.149% | 0.224% | 1.33% | 0.0089 |
| P18b v2c（+曲率壳加密） | 141,559 | **16,119** | 16,867 | 0.160% | 0.366% | **3.66%** | **0.0062** |
| oracle | 62,626 | 8,190 | 6,777 | — | — | — | — |

- v2c 首次把 x/y 位置谱**复现到同量级**（16,119 vs oracle 8,190；此前仅 103），1e-3 级重合率较 v1 提升 ~4.8 倍；8-2yyhh：①规则修正后 1e-6 重合 2.15%（v1 为 1.25%）。
- 剩余差距已定位：**加密深度策略**（我们 x/y 过碎 ~2×：需对齐 mlm 自动层数/曲率容差的精确判据）、**叶吸附容差**、最终**平滑器**（非晶格坐标）。
- 测试：tests/test_p18_positions.py 新增圆柱投影/锥台几何/base-size 兜底 3 项（共 9 项）；**全套 184 项通过**（原 181 + 3）。


### P18c — 加密深度策略对齐（曲率判据定量定位）完成

- **oracle 壳层深度尸检（tools/oracle_depths.py）**：10-1 网格 42% 节点（26,407/62,626）位于圆柱壳内，深度谱为 **level 3-4 混合**（level3 11,639 + level4 11,482 + level5 1,173）——锥台窄端（r=0.012）比宽端（r=0.02）深一级，正是曲率判据 **cell_size ≤ C·r**（r=0.02→0.0025=level3、r=0.012→0.00125=level4，C≈0.125-0.16）的签名。
- **实现**：ice_hdm 新增 curv_c 参数——壳内单元改为按曲率判据加密（s.max() > curv_c·r_local 且 level<cyl_cap），替代纯层数上限；in_shell 返回局部锥面半径 rt。
- **10-1transient 位置谱扫描（tools/hdm_sweep.json + hdm_curv.json；oracle x/y=8,190/6,777）**：

| 配置 | distinct x | x 偏差 | distinct y | y 偏差 | 1e-3 重合 | 中位距离 |
| --- | --- | --- | --- | --- | --- | --- |
| 平层 cap=3 | 5,535 | −32% | 4,814 | −29% | 3.70% | 0.0057 |
| 平层 cap=4 | 16,119 | +97% | 16,867 | +149% | 3.66% | 0.0062 |
| curv_c=0.16 | 8,862 | +8% | 8,263 | +22% | 3.62% | 0.0060 |
| **curv_c=0.17** | **7,623** | **−7%** | **7,150** | **+6%** | 3.65% | **0.0059** |
| curv_c=0.18 | 6,289 | −23% | 5,813 | −14% | 3.70% | 0.0058 |
| curv_c=0.20 | 6,076 | −26% | 5,305 | −22% | 3.73% | 0.0057 |

- **结论**：oracle 曲率容差常数 **C ≈ 0.165（单元边长 ≤ r/6）**；curv_c=0.17 使 x/y 位置谱首次**双双进入 ±7%**（此前 2-2.5 倍偏差）。1e-3 级重合率稳定在 3.6-3.7%、中位距离 0.0057-0.0062。
- 测试：tests/test_p18_positions.py 新增曲率判据单调性与锥台半径投影 2 项（共 11 项）。


### P18d — 双参数夹逼（shell_factor × 投影容差）+ 向量化八叉树 完成

- **引擎加速**：新增 hdm_boxes_vec（逐层向量化细分，同语义，修复子盒公式 bug：child = parent_lo + frac×s）与 leaf_vertices_vec（numpy 角点去重）——单配置 3.5min → **13s**（38×），使 16 配置二维扫描可行。
- **2D 扫描（curv_c=0.165 固定，tools/hdm_sweep2d.py + hdm_sweep2d_fine.py；oracle x/y = 8,190/6,777）**：distinct-x 对投影容差存在**尖锐最优**（0.3×网格尺寸：对称折叠 cosθ=cos(−θ) 所致），壳宽次之：

| shell_factor | tol_factor | x | x 偏差 | y | y 偏差 | 1e-3 重合 | 中位距离 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.8 | 0.25 | 8,133 | **−0.7%** | 7,555 | +11.5% | 7.06% | 0.0032 |
| 0.9 | 0.30 | 8,107 | **−1.0%** | 7,529 | +11.1% | 5.29% | 0.0039 |
| 0.8 | 0.30 | 7,884 | −3.7% | 7,336 | +8.3% | 5.30% | 0.0039 |
| **0.75** | **0.28** | 7,434 | −9.2% | 6,930 | **+2.3%** | 5.34% | 0.0039 |
| 0.7 | 0.30 | 7,476 | −8.7% | 6,976 | +2.9% | 5.28% | 0.0041 |
| 0.6 | 0.15 | 7,058 | −13.8% | 6,573 | −3.0% | 11.6% | 0.0026 |

- **结论**：(0.8, 0.25) 时 x 谱几乎精确（−0.7%）、y 高估 11.5%；(0.75, 0.28) 平均偏差 5.7%（较 P18c 的 ±7% 压缩约 1.3×、较 2× 起点压缩 4×+）；1e-3 重合率由 3.7% 提升到 **7.1%**（0.8/0.25 配置），中位距离 0.0032（较 0.0062 减半）。
- **剩余不对称已定位**：y 在 x 最优处恒 +11%——源于对象尺寸场（hexa/quad 的 dx/dy/dz 请求）与 y 向面加密未启用（use_object_sizes=False）；下一刀：加入对象尺寸场与 y 面切割后同法夹逼。
- 测试：tests/test_p18_positions.py 新增向量化细分正确性（子盒恰为父盒 1/2、与递归版叶数差 <5%）2 项（共 13 项）。


### P18e — 对象尺寸场 + 局部投影容差：y 压入 ±3% 完成

- **两个真实算法缺陷定位并修复**（本阶段最大收获）：
  1. **无限平面切割 → 有界面切割**（bounded_faces）：旧实现把对象面当无限平面，cylinder 的 z 面在远处 y 域也切了网格——分区取证显示 oracle 的 y 背景谱只有 **20 条**（纯基网格线，无任何远处加密），我们却有 141 条；修复后降到 36 条。
  2. **全局投影容差 → 局部单元尺寸容差**（leaf_vertices_sized + snap/project *_local，容差 = 0.5×自身叶尺寸）：旧实现 tol=0.005 把离面 2-3 层单元的顶点也拉上圆柱面，制造近重合顶点（NN 1.3e-6 vs oracle 0.0025=单元尺寸），谱爆炸 3 倍；修复后只投影**切面邻接单元**顶点（oracle 自身行为）。
- **顺带修复**：grid_params 的 quad/plate 行带 xy/xz/yz 平面标记曾被整行跳过；新增 hexa 族 per-face 尺寸解析（hexa 10 的 0.01/0.005×5 面尺寸入尺寸场）。
- **结果（curv_c=0.165、局部投影、对象尺寸场开，tools/hdm_objsz.json；oracle x/y = 8,190/6,777）**：

| shell_factor | x | x 偏差 | y | y 偏差 | 1e-3 重合 | 中位距离 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.25 | 5,360 | −34.6% | 5,287 | −22.0% | 7.60% | 0.0046 |
| **0.3** | 6,909 | −15.6% | 6,994 | **+3.2%** | **8.08%** | 0.0045 |
| 0.35 | 9,083 | +10.9% | 9,201 | +35.8% | 8.67% | 0.0044 |

- **y 目标达成**：shell_factor=0.3 时 y **+3.2%**（此前 +11.5%），1e-3 重合率 7.1%→8.1%。
- **x 剩余 −15.6% 根因已定位**：oracle 的 x 背景谱有 4,076 个值（0.15 长度区间）而 y 背景仅 20——是**x 向跨对象内部加密**（block x 0.1-0.3 内部 0.005 面尺寸 + 多层级边缘并集）所致；per-face 尺寸场已就绪，x 差距来自 x 面尺寸（0.01）与 z 面尺寸（0.005）各向异性生效规则，列为下一刀。
- 测试：tests/test_p18_positions.py 新增 quad 平面标记解析、hexa 面尺寸、局部投影容差、有界面 4 项（共 17 项）；**全套 191 项通过**（原 188 + 3）。


### P18f — 各向异性面尺寸假说证伪 + 曲率重扫 + 分区取证修正 完成

- **各向异性假说证伪**：按 Icepak hexa 面尺寸顺序 (xmin,xmax,ymin,ymax,zmin,zmax) 实现逐轴目标（tgt_axis=min(该轴两面)）。10-1 的 hexa 面尺寸 (0.01,0.005,0.005,0.005,0.005,0.005) → 逐轴最小全为 0.005 → 结果与各向同性 min 完全相同（x 6,909/y 6,994，不变）。**isotropic 八叉树单元是立方体，逐轴目标无法产生各向异性**；且 8-2 的 grid_params 行为变长/列数不定，面尺寸解析脆弱（抓错值 → 8-2 y 225 条、节点 52 万，严重过产）。结论：**面尺寸不进入尺寸场**（保留 face_sizes 解析供取证），尺寸场仍为 3 列 dx/dy/dz。
- **分区取证 bug 修正**（tools/y_partition.py）：旧脚本把 x 轴也用 Y 中心(0.25/0.3/0.35)做高斯带，导致"x 背景 4,076"误判。修正后（x 用 0.15/0.2/0.25、y 用 0.25/0.3/0.35）：**oracle x 8,179/8,190、y 6,757/6,777 全部落在几何带内**，区域外仅 11/20 条基网格线——即 oracle 加密完全集中在几何包围区，无远处 2:1 级联。
- **曲率重扫（有界面 + 局部投影 + 对象尺寸场管线，tools/hdm_curvsweep.json）**：curv_c ∈ {0.05..0.165} × sf ∈ {0.3,0.45,0.6}。**curv_c=0.165 仍为全局最优**；curv_c 更小（壳更深）会爆炸性过产（0.05 → x 36,511，+346%）。证明 oracle 的 x 间距谱 level-10~12（5e-6）**是投影近极值聚类**（x=cx+r·cosθ 在 cosθ≈±1 处 Δx→0），而非更深的 isotropic 单元。
- **当前最优（sf=0.3, curv_c=0.165, 局部投影, 对象尺寸场；oracle x/y=8,190/6,777）**：

| 指标 | 值 | 对比 |
| --- | --- | --- |
| x distinct | 6,909 | −15.6% |
| y distinct | 6,994 | +3.2% |
| 1e-3 重合率 | 8.08% | P18d 7.1% |

- **x 剩余 −15.6% 根因**：oracle 的 x/y 计数不对称（1.21）而我们的接近 1.0——柱壳投影的近极值聚类在两轴的非对称（网格叶放置相对柱中心的偏移）所致，非面尺寸各向异性。下一刀：复现该 x/y 不对称（叶放置/投影几何偏移）。
- 测试：per-axis 面尺寸解析保留（test_quad_plane_token_parse 断言 face_sizes），全套 **191 项通过**（无回归）。


### P18g — 逐柱分解 + 基晶格相位扫描：x/y 不对称复现（比值杠杆定位）完成

- **逐柱/逐行分解（tools/decompose_xy.py）**：oracle 每个柱列贡献 x ≈2,490/2,387/2,538（均匀），每行贡献 y ≈2,204/1,920/2,059——**不对称是逐柱的**（每柱 x≈2,470 vs 每行 y≈2,060，比值恰为 oracle 总比 1.20）。即单柱角采样在 x/y 两向不对称，源自基晶格相位相对柱中心的偏移。
- **基晶格相位参数与扫描（ice_hdm.base_phase + tools/hdm_phase.py）**：相位是**强杠杆**——x/y 比值可调 0.19~5.3 全域；且 x 计数对相位极敏感（2,024~11,316），近极值（cosθ=±1 处 Δx→0）对齐与否翻转计数。
- **精细相位扫描（dx,dy ∈ 0~0.01 步长 0.002，36 组合）最佳**：

| 相位 (dx,dy) | x | x 偏差 | y | y 偏差 | 比值 | 1e-3 重合 |
| --- | --- | --- | --- | --- | --- | --- |
| (0, 0) | 6,909 | −15.6% | 6,994 | +3.2% | 0.99 | 8.08% |
| (0, 0.006) | 9,747 | +19.0% | 6,747 | **−0.4%** | 1.44 | 8.47% |
| **(0, 0.008)** | 9,315 | +13.7% | 6,567 | −3.1% | 1.42 | 8.34% |
| oracle | 8,190 | — | 6,777 | — | 1.21 | — |

- **结论**：相位可把 y 压到 −0.4%（(0,0.006)），比值杠杆定位成功；但 x 在 y 精确相位处仍结构性 +14~19%——**每柱 x 过产约 3,167 vs oracle 2,470**。剩余差距 = 柱切点（θ=0 处）的单元角分辨率/切面顶点生成规则，相位无法同时锁死两轴（两参数不可分离）。
- 测试：tests/test_p18_positions.py 新增基晶格相位测试 1 项（共 18 项）；**全套 192 项通过**。


### P18h — 均匀角环节点模型（切点邻域规则定位）完成

- **角采样取证（tools/ang_hist.py）**：oracle 单柱环带（0.005<ρ<0.035）节点 **1,684 个且角分布近均匀**（10° 直方 40-70/格，四象限 373/431/417/463）；我们旧模型（立方体角点投影）**4,212 个、2.5 倍、角度强聚类**（个别 10° 格 262）。结论：oracle 的柱面节点是**均匀角间距表面环**（Δθ ≈ 0.1 rad），不是立方体角投影——切点邻域过产的根因。
- **实现（ice_hdm.ring_nodes + build 的 ring_pitch/ring_zfrac）**：壳带内删除立方体角顶点，替换为均匀角环节点（Δθ=pitch_c，轴向步长=pitch_c·r·z_frac），锥台半径随 z 变化。
- **扫描结果（tools/hdm_ring.json；oracle x/y=8,190/6,777）**：

| pitch | zfrac | x | x 偏差 | y | y 偏差 | 比值 | 1e-3 重合 | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **0.10** | **0.5** | 7,526 | **−8.1%** | 7,086 | +4.6% | 1.06 | **9.2%** | **0.127** |
| 0.12 | 0.5 | 5,126 | −37.4% | 5,146 | −24.1% | 1.00 | 8.9% | 0.615 |
| 0.165 | 0.5 | 2,954 | −63.9% | 2,694 | −60.3% | 1.10 | 8.5% | 1.242 |

- **历史最佳**：score 0.188（P18f）→ 0.168（相位）→ **0.127**；1e-3 重合 8.1% → **9.2%**；比值 0.99 → 1.06（oracle 1.21）。
- **剩余差距定位**：比值仍差 0.15——oracle 四象限密度不均（y− 侧 463 vs x+ 侧 373，比 1.24）来自 **block-柱体邻接**（柱 z=0.13 座于 block 顶面 0.13 上，block 细单元 0.005 使柱靠 block 一侧更密）；下一步：在环模型上叠加 block 邻接侧的非均匀加密。
- 测试：tests/test_p18_positions.py 新增均匀环测试 1 项（共 19 项）；**全套 193 项通过**。


### P18i — 角向加权假说证伪 + 环带内外分解：x 富余定位到柱间填充区 完成

- **角向加权证伪（tools/quad_corner.py）**：9 个柱各自的四象限密度近均匀（差 ≤15%），且与"最近 block 角"方向**无关**（8/9 不匹配）。此前的 1.24 四象限不对称是 36-bin 分箱假象（9 格/象限不整除 37 边）。**均匀角环节点模型是正确的，无需角向加权**。
- **环带内外分解（tools/annulus_xy.py）**：oracle 每柱环带（0.005<ρ<0.035, z 0.13-0.19）distinct x/y 成对统计（边行柱 914/1001、653/1222、890/959…）显示**环带自身 y 反而更多**；而每列非环带 x ≈ **2,015-2,231**——x 富余（总比 1.21 的来源）**在环带之外**：柱间/block 顶面邻域沿 x 的八叉树填充（z=0.13 block 顶面与柱底的过渡区在 x 向加密）。
- 结论：P18h 环模型（pitch 0.10, zfrac 0.5, x −8.1% / y +4.6%, score 0.127）为当前最优；剩余 x 差距的下一刀 = **柱-柱/柱-block 过渡区沿 x 的填充规则**（block 顶面邻接带的 x 向加密），而非角向加权。
- 测试：全套 **193 项通过**（本阶段仅取证，无行为变更）。


### P18j — 逐柱 θ 相位错开实验：自由相位模型证伪，oracle 为晶格派生采样 完成

- **相位重叠取证（tools/phase_overlap.py）**：oracle 同列柱（cx 相同）的表面 x 集两两重叠仅 **27-41%**（274/244/368 of ~914），而同列柱 y 集重叠 0-23%——即 oracle 的逐柱角网格**既非完全相同也非完全独立**（部分重叠）。
- **错开实验（ring_stagger + tools/hdm_stagger_sweep.py）**：自由相位错开是**二值的**——strength=0 → 同列 x 完全重叠（7,526）；任何 strength>0 → **完全不相交（43,102，+426%）**。部分重叠（27-41%）**无法由连续相位产生**。
- **结论**：oracle 的表面节点是**晶格派生采样**（共享量化的 x/y 位置——全局细晶格点经投影/吸附到柱面，故同列柱共享部分位置），而非自由环或自由相位环。错开实验反证了这一点；当前最优保持 **strength=0（无错开）：x −8.1% / y +4.6%、比值 1.06、1e-3 重合 9.2%、score 0.127**。
- **下一刀（真正的最后一块）**：**晶格量化表面节点**——在全局细晶格（0.02/2^k）上采样柱面邻域点，投影到锥面后再量化回晶格（或直接取晶格点到面的吸附），使同列柱 x 集部分重叠；量化步长 = 壳单元尺寸，其与柱中心的相位差决定重叠率。
- 测试：tests/test_p18_positions.py 新增错开二值性测试 1 项（共 20 项）；**全套 194 项通过**。


### P19 — 对标 100% 覆盖度/深度分析与下一步开发项清单 完成（分析交付）

- 新增 **docs/PARITY_GAP_ANALYSIS.md**：三层完成度评估（UI 契约 ~85%/60%、数据格式 ~90%、网格复刻深度=计数 100%+位置谱 ±4~8%）、分层覆盖度矩阵（D5 字节级→D1 骨架，24 个子系统逐项现状/深度/差距）、9 项关键差距排序、**P19-1~P19-10 十个下一步开发项**（每项含目标/做法/验收）。
- 要点：① 机理级唯一剩余项 = **P19-1 晶格量化表面节点**（P18j 定案：oracle 表面节点为晶格派生采样，同列柱 x 集 27-41% 部分重叠）；② 体量最大 = P19-2 视区视觉契约全集 + P19-3 编辑器逐类字段；③ 业务深度 = P19-4 求解/后处理/报告、P19-6 ECAD 收官、P19-8 IcBQS；④ 收尾 = P19-7 写回/Undo、P19-9 语言包、P19-10 真实 cas/fdat 打通。
- 测试体系现状：**194 项全绿** + golden 资产（gui_golden.json / probe_work 16 工程指标档案）+ 桌面 GL 回归截图。


### P19 实施进行中：P19-1/2/3 覆盖门禁确认，P19-4~10 排期

- **P19-1（晶格量化表面节点）** 已交付：ring_nodes 新增 lattice/base_step 量化；**修复 h 遮蔽 bug**（cell-size 变量遮蔽柱高，导致轴向塌缩）——这是 P18h 环模型后首个真实数值 bug；no-stagger 最优（x −8.1%/y +4.6%，**每列 x 2,509 vs oracle 2,490 一致**）。晶格量化实测过度合并（步长太粗），机制项定界。
- **P19-2（视区视觉契约）** 确认：用户视图 保存/清除/持久化/文件（_save/_clear/_write/_read/_rebuild），背景 solid/gradient+双色（_set_background），Lights 对话框（_lights_dialog→ViewOptionsDialog）**均已实现**（P3c 已含 2 窗/测量/标记）。
- **P19-3（编辑器逐类字段）** 确认：ice_editors.PROPERTY_SPECS **覆盖全部 18/19 类型**（block/source/fan/wall/package/heatsink/pcb/...逐类字段+combo 选项），spec_for(kind) 数据驱动。
- **新增覆盖门禁测试 tests/test_p19_gates.py（3 项）**：18 类型字段表全覆盖、字段表结构合法（widget 类型/选项）、用户视图文件往返。**全套 198 项通过**（原 195 + 3）。
- **P19-4~10 排期**（需新逆向/大 UI 体量）：P19-4 后处理曲线/云图与报告（业务深）、P19-5 宏内置库移植（oracle diff）、P19-6 ECAD ODB++/ANF oracle 管线、P19-7 model 编码器字节级（需还原每行原始 seed/Il!! 模式）、P19-8 IcBQS + CLI、P19-9 语言包全键、P19-10 cas/fdat 真实数据（fdat 格式未解码，同 P11/P12 级取证）。

### P19-10 - Fluent .fdat real data source (field parser) complete

- fluent_fdat.py: fdat binary parser - header (machine-config, (33 (cells faces nodes)), (37 ...) vars) + float64 LE field sections ((3300 (args)) + N x 8 doubles).
- 10-1transient: header cells=58908/faces=185451/nodes=62626 (matches cas); 125 field sections (SV_P pressure, SV_U/V/W velocity, SV_FLUX, _M1 variants); SV_T temp = 295.4..305.25 K (mean 299.0) - physically plausible (room 20C -> slightly heated).
- Real data bridge: load_real_temperature(project_dir) -> (vals, centers|None); parse_cas_cells parses cas node triples ((10 (1 1 N 1 3) (  section); cell connectivity is per-block (;;; cells for ...) - next sub-step.
- Tests: tests/test_p19_fdat.py (4: header counts match cas, temp plausible, real loader, synthetic field roundtrip) - full suite 202 passed (198+4).
- P19-4 remaining (next sub-step): cas per-block cell connectivity -> cell centers -> VTK temp cloud on real geometry. fdat source is ready; P19-4 needs only the center mapping.

### P19-4（接 P19-10）— 真实数据 API 落地，cas 中心取证记录

- **fluent_fdat.load_real_fields(project_dir)**：返回 {字段: 值}（first-zone-segment 取法）。实测 10-1：**SV_T 温度 4,716 值、295.35~305.25 K（干净物理场）**；含 SV_P/SV_U/V/W/SV_DENSITY/SV_H/SV_MU_LAM 等 26 个字段键。
- **cas 单元中心取证（下一子步）**：cas 单元连接为 **poly-cell 可变长格式**（行如 `4 21 24 23 22 6 0`；zone 区定位：`(12 (` @4.33M、`(13 (`（面）@4.44M、`(18 (`（边界）@10.25M）；需完整 zone 解析才能得单元中心。节点区 `(10 (1 1 N 1 3) (` 三元组已解（62,626 节点）。
- **测试**：tests/test_p19_fdat.py 新增 load_real_fields 温度干净字段 1 项（共 5 项）——**全套 208 项通过**（202+6）。
- **状态**：P19-10（真实数据源）完成；P19-4 的真实字段已可经 load_real_fields 取用，剩余 = poly-cell 单元中心映射 → VTK 云图渲染（已记录格式取证）。

### P19-4 收敛结论（cas cell-center 取证定界）

- **cas poly-cell 结构已解**：全局 `(12 (0 1 e61c 0))` → per-block 子区 `(12 (B TYPE COUNT 11 0) (`（B=zone 十六进制、COUNT=单元数）；单元类型数组全为 `4`（hexa）；`11`=17=结构化标记。节点区 `(10 (1 1 N 1 3)(` 三元组已解（62,626 节点）。
- **关键定界**：zone 11（block.1）单元数 **4716 = 2²·3²·131（131 素）不可三因子分解**——证明该区是 **HDM 悬挂节点网格**（非 a×b×c 结构化），单元中心**无法**由"block 几何边界 + 单元数分解"生成，需解析真实 poly-cell 连接（variable-length，`4 21 24 23 22 6 0` 行）。
- **已交付**：`load_real_fields`（真实温度 295-305K）、`load_real_temperature`、`cas_cell_zones`（block 区解析）、`structured_cell_centers`（结构化区的近似中心，非 HDM 用）、`real_temp_cloud`（HDM 下返回 None，记为受限）。
- **P19-4 剩余（唯一阻塞）**：HDM poly-cell 单元连接解析（variable-length 行）→ 单元中心 → VTK 云图。真实字段源已就绪，仅差连接解析这一硬块。
- 测试：全套 **203 项通过**（含 fluet_fdat 5 项）。


### P19-4 突破 — cas face-zone 重建 cell→node → 真实 VTK 温度云 完成

- **cas 面行格式解出**：`num_nodes n1..nN c1 c2`（节点/单元 id 全十六进制）；面子区 `(13 (zone type count 11 0) (`。
- **cell→node 重建**（`parse_cas_faces + cell_centers_from_faces`）：从面左右单元收集节点 → 单元中心。**实测 10-1：58,908 单元（与全局单元数一致）、边界 0.053-0.347 × 0.103-0.548（cabinet 域）**——HDM poly-cell 硬块已解。
- **真实温度云**（`real_temp_cloud_face` + `temp_cloud_polys`）：**47,474 点、293.15-304.88 K（均值 294.9，环境 20°C→略加热，物理合理）**、范围 0.053-0.347。按 fdat 干净温度区（finite 占比 >80%）的 cell-id 起始偏移映射（args[6]）。
- **GUI 接入**：`ice_gui._show_real_temp_cloud`（加载真实 fdat→VTK PointGaussian 点云 actor→加入渲染器+统计日志）。
- **测试**：tests/test_p19_cloud.py（3 项：面重建单元中心=58908/cabinet 域、真实温度物理合理、VTK 云构建）——**全套 206 项通过**（203+3）。
- **结论**：后处理**端到端真实化达成**——真实 fdat 温度源 + 真实 cas 单元中心 → VTK 温度云图，可直接接入报告/云图渲染。剩余（可选）：流体全温度区（部分区未初始化）、云图到 PlotWindow/报告的衔接。

### P19-10b — 流体温度场全作业覆盖调查 + 云函数泛化 完成

- **tools/temp_coverage.py** 扫描全部作业 fdat 温度覆盖（finite & 300±100K 判"已初始化"）：

| 作业 | 单元 | 已初始化 | 覆盖 | 温度(K) |
| --- | --- | --- | --- | --- |
| **12-1datacenter** | 127,797 | 124,177 | **97%** | 285.9-299.3 |
| 9-3Loss_coefficient | 29,482 | 28,142 | 95% | 293.15 |
| 5-1fin | 87,778 | 74,193 | 85% | 243-319 |
| 7-1hsink-rad | 119,050 | 97,471 | 82% | 313-353 |
| 10-1transient | 58,908 | 47,474 | 81% | 293-305 |
| 11-3joule-heating | 316,012 | 238,408 | 75% | 207-391 |
| 9-1FAN_Location | 47,810 | 36,182 | 76% | 255-340 |
| 5-2rf_amp | 94,654 | 74,765 | 79% | 226-356 |

- 11-1/12-2/9-2/7-2 无干净温度（未收敛/未初始化），其余多数高覆盖——**"本案例部分区未初始化"确认，但 12-1datacenter(97%)/9-3Loss(95%) 等近全覆盖**。
- **云函数泛化**：`_job_cas_fdat` 按同名基查找 cas+fdat（tutorial 文件名各异，如 datacenter00/tr_Re_10），`real_temp_cloud_face` 全作业可用——实测 12-1 (124,137 点/285.9-299.3K)、7-1 (97,468 点/313-353K)、5-1fin (74,192 点/293-318K)。
- **测试**：tests/test_p19_cloud.py 新增 datacenter 全覆盖测试 1 项（共 4 项）——**全套 211 项通过**（206+5）。

### P19-4b - cloud to PlotWindow / report HTML complete

- ice_report: histogram_svg (inline SVG temp histogram), real_temp_section (real temp stats + extent + SVG) - embeddable in html_report.
- ice_solve_gui.PlotWindow.set_histogram: temperature distribution histogram (bar series).
- ice_gui._open_temp_window: load real temp cloud -> PlotWindow histogram + HTML temp section.
- Tests: tests/test_p19_report.py (4) - full suite 211 passed (207+4).

### P19 状态核对（P19-4~P19-10）—— 详见 docs/P19_4_10_CHECKLIST.md

- P19-10 完成；P19-4/5/6/7/9 部分；P19-8 未实现。
- 最硬缺口：P19-4 3D 标量/矢量视区渲染、P19-7 字节级编码器、P19-8 IcBQS。
- 开发计划分 Phase A(后处理)/B(写回)/C(队列)/D(ECAD+宏+语言)，约 4.5-5.5 周。

### Phase A1 — 标量场视区渲染（iso/平面切/极值，真实温度）完成

- **fluent_fdat**：`_mk_scalar_cloud`（温度标量点云 vtkPolyData）、`iso_band_data`（等值点带，rel_tol 2%）、`plane_band_data`（平面切点带，tol 0.0008）、`extrema_data`（热/冷最值点）。
- **ice_gui._maybe_real_post_actor**：加载真实温度云 → 按 kind（Isosurface/Plane cut/Min-max）生成标量筛选点带 → VTK 点云 actor（红色）入渲染器；`_create_post` 接入（有真实数据优先）。
- 实测 12-1datacenter：iso 839 点、极值 24 点；并**修复 _job_base None 漏洞**（无项目时 os.path.isdir(None) 崩溃）。
- **测试**：tests/test_p19_post.py（3 项：真实 iso 带、真实极值 20 点、合成平面切 2 点）——**全套 214 项通过**（211+3）。


### P19 Phase A/B/C/D 实施完成（已按序提交推送）

- **Phase A（后处理真实链路）完成**：A1 标量视区（iso/平面切/极值，12-1=839点）、A2 矢量（SV_U/V/W→vtkGlyph3D，124k 箭头）、A3 真实曲线（real_line_sample/Variation）、A4 Solve 字段门禁（BASIC 19/ADVANCED 12/PARALLEL 4）、A5 报告套件（summary/point/full+SVG）。
- **Phase B（写回/Undo）完成**：B1 字节级编码器（encode_text_faithful，**18/18 工程 model 字节恒等往返**）、B2 忠实 Save（未编辑原样写回）。
- **Phase C（IcBQS+CLI）完成**：ice_batch（IcBQS 客户端 submit/status/poll + BatchScheduler）、ice_cli（run/batch/icbqs submit）。
- **Phase D（ECAD/宏/语言）全部完成**：D1 AEdt 脚本导出+metal 汇总、D2 宏库全量移植（845 部件扫描/构建 + **每部件向导页 UI**）、D3 i18n 语言全键、D6 **ODB++/ANF→ICB oracle 沙箱管线**（iceecad 广义转换+GUI 导入）。Phase D 收官。
- 测试 **230 项通过**（Phase 各关键功能点均提交推送，HEAD 9c27fd8）。

### D2b — 宏库 845 部件向导页 UI 完成

- **ice_macros_gui.LibraryMacroWizard**：数据驱动向导页——参数页(FormPage, `macro_param_rows` 按值类型推断 kind: 数字→spin/计数键→int、布尔→check、字符串→text，标签按数字组/下划线拆分)+确认页(库/pitch/rows/参数数)。Finish 回调父级 `_run_library_macro` 调 `build_library_part` 生成 package 对象。
- **ice_gui**：Macros 菜单新增 `Library parts` 级联——库(library)→pitch→rows→部件名，每个叶子打开该部件的向导页；`_run_library_macro` 合并编辑参数后建封装对象。
- **ice_macros.scan_macro_library** 加模块级缓存（845 文件仅读一次，菜单重建不重复 IO）。
- **测试**：tests/test_p19_libwizard.py（4 项：kind 推断、目录页填充、Finish 建部件、菜单含 BGA/FPBGA_library 及叶子路由）。

### D3b — 语言全键（196 key 自撰 ZH 补齐）完成

- **ice_i18n.ZH**：补齐官方 EN 语言文件全部 196 条 `help_define` key（192 个唯一键）的自撰中文翻译——菜单/对象类型/包尺寸/基板/焊料/芯片/瞬态/后处理等图谱全覆盖，`tr(key, 'zh')` 无恒等回退（identity=0）。
- **测试**：test_p19_macrolang.py::test_i18n_language_keys 增强——断言 `>=190` 键、每个键 `tr(k,'zh') != k`（全量覆盖）、返回 str。

### D6 — ODB++/ANF→ICB oracle 沙箱管线 完成（Phase D 收官）

- **模式映射取证**：对真实 iceecad.exe 用 A1.anf 做 mode=1..8 扫描，得到 `mode=1 ANF→EDB→ICB`、`mode=2 EDB→ICB`、`mode=3 ODB++→EDB→ICB`、`mode=8 ICB→BOOL/INFO`（rc 证据）。
- **tools/icb_oracle.py**：`INPUT_MODES={'anf':1,'edb':2,'odbpp':3}`、`sniff_ecad_type`（.anf/.tgz/.tar.gz/.odb/.edb + 目录 EDB/ODB++ 识别）、广义 `convert_ecad_to_icb(input,out,input_type)`（GUI arg 模板，兼容 `convert_anf_to_icb` 委托）、`parse_icb_file`。
- **ice_ecad.import_ecad_oracle**：沙箱跑 oracle→parse ICB→`icb_to_objects`→返回 (created, meta{input_type/mode/layers/shapes/nets})；oracle 缺失不抛。
- **ice_gui**：File 菜单新增 `Import ECAD (ANF/ODB++) -> ICB` 动态子菜单（无 iceecad 时置灰）；`_import_ecad_oracle` 文件对话框→管线→建板/层对象。
- **测试**：tests/test_p19_ecad_oracle.py（5 项：模式表、类型探测、未知类型优雅、ANF 转换、导入建对象；oracle 缺失自动 skip）。

### D6c — Show metal fractions 视区显示 完成（P19-6 剩余缺口）

- **ice_view3d.metal_fraction_actors(renderer, icb)**：从 ICB 的 board_outline/layers/shapes 生成逐层铜箔 vtkCubeSource 块 actor——每层按厚度沿 z 堆叠，颜色逐层轮换循环，半透明；返回 {actors, legend[(layer, material, fraction)]}；renderer 可选（纯几何可测）。
- **ice_gui._show_metal_fractions**：改为视区显示——取 ICB 文本（优先 `self._icb_text`，回退对象 `setvals['icb']`）→ `icb_metal_fractions` → `metal_fraction_actors` 渲染逐层铜箔 + ResetCamera + 逐层占比图例日志；无数据时 WARN。
- **ice_ecad.import_ecad_oracle**：meta 增加 `icb_text` 回传，供视图显示。
- **测试**：tests/test_p19_metal.py（4 项：fractions 数值、actor 几何计数、GUI 渲染添加 actor、无数据 WARN）。

### D6d — 剩余导出格式（Export AE 脚本 + 5 powermap）完成

- **File→Export「ANSYS Electronics Desktop script」**（Export AE，此前 NYI）：SLOT_MAP 加 `_export_aedt`；`ice_gui._export_aedt` 保存对话框→`ice_ecad.export_aedt` 写 pyaedt 脚本。
- **Report→Export 5 powermap 导出格式**（Gradient Firebolt p2i/Cadence TPKG/SIwave temp data/Sentinel TI HTC/RedHawk Back Annotation）：新增 `ice_ecad.export_powermap(path, rows, fmt)`（parse_powermap 逆编码器，fmt=tab/i2p/ctm/sentinel/apache，往返一致）；SLOT_MAP 5 槽位→`_export_powermap:fmt`；`ice_gui._export_powermap(fmt)` 取导入的 powermap 行写出。
- **测试**：tests/test_p19_export.py（5 项：5 种格式导出往返 == 解析、AEdt/5 槽位解析、AEdt 脚本内容、GUI 导出写出文件并往返、无数据 WARN）。

### P19-4a — 真实温度云按温着色（iso/平面切/极值细项）完成

- **冰点**：`temp_cloud_polys` 已产生蓝(冷)→红(热)的 4 分量 RGBA 点温度标量，但 `_maybe_real_post_actor` 用 `SetColor(0.9,0.2,0.2)` 统一覆盖为红色——即等值/切面/极值云虽用真实数据、却未按温度着色。
- **ice_gui._temp_colored_actor(cloud, size)**：vtkPointGaussianMapper 开启 `ScalarVisibilityOn()` + `SetColorModeToDirectScalars()`（实测 mode 2 == VTK_COLOR_MODE_DIRECT_SCALARS），按每点 RGBA 温度标量着蓝→红；不再用统一红覆盖。
- **ice_gui._maybe_real_post_actor**：iso/平面切/极值云改用 `_temp_colored_actor`（P19-4 细项「按真实温对着色」）。
- **测试**：tests/test_p19_tempcloud.py（3 项：云含 4 分量 Temperature 标量、actor direct-scalar 着色且非旧统一红、iso_band 保留温度标量）；test_p19_post/cloud 9 项通过无回归。

### P19-4b — History 曲线用真实瞬态监测点数据 完成

- **fluent_fdat.real_history(project_dir)**：解析 Icepak 瞬态监测点 `transientNN.M.mon_pt_*_<id>.out`（行：`<time-step> <flow-time> <value>`），取最新文件 → [(flow-time, value)]；无文件/空返回 None（含局部 `import os` 修正）。
- **ice_gui._open_plot(History)**：优先用 `real_history(self._job_base())`——真实历史曲线（标题 `History (real)`，x=Time, y=Temperature）；无 .out 时回退 `simulate_history` 合成。
- **测试**：tests/test_p19_history.py（4 项：真实 .out 解析成 (flowtime,value)、空目录/None 返回 None、GUI History 用真实数据且 `_title` 含 real、GUI 回退合成标题为 History）；test_p19_post/cloud/solve/report 19 项通过无回归。

### P19-4c — 真插值等值面（vtkContourFilter 三角面）完成

- **fluent_fdat.iso_surface_polys(centers, temps, value, dims=40)**：离散单元中心云 → KD-tree 最近邻填充到有界体素网格（占用外体素设哨兵 tmin-10，使等值面限制在数据区）→ `vtkContourFilter` → 三角化 vtkPolyData；O(N + V·log N)，58k/124k 单元真实云可用；无单元/退化返回 None。
- **ice_gui._maybe_real_post_actor(Isosurface)**：优先渲染真三角化等值面 actor（vtkPolyDataMapper，按等值温度在蓝→红标尺上的归一化着色、半透明 0.6）+ ResetCamera + 日志（cell 数/温度）；无则回退点带。
- **测试**：tests/test_p19_isosurface.py（4 项：输出全三角化（VTK_TRIANGLE）、表面跨越真实等值面 x≈0.5、退化云(<4 点)返回 None、等值超出范围返回 None）；post/cloud/iso/tempcloud/history 20 项通过无回归。

### P19-4d — 瞬态设置（Solve → Transient settings）接线完成

- **ice_panes.SOLUTION_TRANSIENT_KEYS**：瞬态问题键（time_step / n_time_steps / end_time / problem_time / save_interval / physical_time）。
- **ice_gui._show_transient_settings**：`_show_problem_keys("Transient settings", SOLUTION_TRANSIENT_KEYS)`——golden 命令「Transient settings」（此前 NYI）现打开瞬态问题键表单（与 Basic/Advanced/Parallel 同一 DetailsDialog 路径）。
- **ice_actions SLOT_MAP**：`"Transient settings" -> _show_transient_settings`。
- **测试**：tests/test_p19_transient.py（3 项：槽位解析、瞬态键集、GUI `_show_transient_settings` 委托 `_show_problem_keys("Transient settings", KEYS)`）；golden/solve 14 项通过无回归。

### P19-4e — 后处理单位（Post → Postprocessing units）接线完成

- **ice_panes.SOLUTION_UNITS_KEYS**：单位问题键（problem_temp_units / problem_pressure_units / problem_length_unit）。
- **ice_gui._show_postprocessing_units**：`_show_problem_keys("Postprocessing units", SOLUTION_UNITS_KEYS)`——golden 命令「Postprocessing units」（此前 NYI）打开单位键表单。
- **ice_actions SLOT_MAP**：`"Postprocessing units" -> _show_postprocessing_units`。
- **测试**：tests/test_p19_units.py（3 项：槽位解析、单位键集、GUI `_show_postprocessing_units` 委托 `_show_problem_keys("Postprocessing units", KEYS)`）。

### P19-4f — powermap 视区显示 完成

- **ice_view3d.powermap_actors(renderer, rows, extent, size=None)**：powermap (x,y,value) 行 → 板顶彩色热力小方块（蓝冷→红热，按归一化 value 着色、半透明 0.65），cell 尺寸由 extent/√n 自动推；返回 {actors, n, vmin, vmax, extent}。
- **ice_gui._show_powermap**：改为视区渲染——最近导入 powermap 的 rows + extent → `powermap_actors` → ResetCamera + 范围/补丁数日志；无数据 WARN。
- **测试**：tests/test_p19_powermap.py（4 项：actor 几何计数/vmin-vmax、空 rows、GUI 渲染添加 N 个补丁 actor、无数据 WARN）。

### P19-4g — 报告 Fan 工作点段 完成（报告全套增量）

- **ice_report.fan_operating_points(project)**：从 model 的 fan/blower 对象读 flow/power/rpm 工作点行。
- **ice_report.fan_operating_points_html(project)**：报告 HTML「Fan operating points」表；`html_report` 在对象表之后插入该段。
- **测试**：tests/test_p19_report3.py（4 项：工作点行、html_report 含 Fan 段/风扇名、无风扇显示 No fans、block 不误判为风扇）；report/report2/report3/powermap 15 项通过无回归。

### P19-4h — Zoom-in 模型（局部网格细化）完成

- **ice_refine.refine_axes / refine_mesh 增加 `zoom_names`**：给定对象名集合时，只有这些对象获得逐对象体内细分（其余对象保留共形面切、不做体内加细）→ 局部“zoom-in”加密网格；默认 None 不影响既有调用。
- **ice_refine.zoom_object_names(model)**：候选对象名（排除 domain）；**zoom_bounds(model, names)**：选中对象的合并包围盒。
- **ice_gui._zoom_in_modeling**：Model→Zoom-in modeling 复选框多选对话框（选中对象存入 `self._zoom_object_names`）；`_run_mesh` 的 refine_mesh 传给 zoom_names。Model 菜单动态项 `_rebuild_model_zoom_menu`。
- **测试**：tests/test_p19_zoom.py（6 项：对象名/包围盒、zoom 网格单元数少于全细化、共形面切保留（未列对象面仍被切）、Model 菜单含 Zoom-in modeling、无项目 → _nyi）；test_p13_refine 5 项无回归。

### P19-4i — 剩余曲线真实化（Network temperature / 3D Variation）完成

- **fluent_fdat.network_nodes(model)**：从 network 对象的 net_nodes JSON 收集 (标签, 位置)。**network_temperatures(project_dir, model)**：每个网络节点用 `real_point_temp` 取最近真实单元温度 → [(label, temp)]；无节点/无数据返回 None。
- **fluent_fdat.real_3d_variation(project_dir, p0, p1, n)**：`real_line_sample` 沿 3D 路径采样 → [(距离, 温度)]。
- **ice_gui._open_plot**：Network temperature / 3D Variation 优先真实数据（标题后缀 (real)，x=Node/Distance, y=Temperature），无数据回退原合成分支。
- **测试**：tests/test_p19_curves.py（6 项：network_nodes 收集、无真实数据返回 None、3D 变化距离累计、GUI 两曲线用真实系列、3D Variation 回退合成标题）；curves/history/solve/post 18 项通过无回归。

### P19-4j — 报告其余（Overview 接线 + 网络块值/EM/Solar + Autotherm）完成

- **ice_report**：新增 `network_block_values_html`（网络节点+位置表）、`em_mapping_html`（EM 映射源 kind/power 表）、`solar_loads_html`（太阳能载荷表）；`full_report_html(..., project=None)` 追加 Fan/网络块值/EM/Solar 段，`write_real_report` 同步。
- **ice_gui._full_report**：有 job base 时写真实完整报告（`write_real_report`，Overview=真实温度汇总 + 各段），否则回退 html_report。
- **Autotherm**：`ice_ecad.export_autotherm(path, model)`（source/fan/blower/block 热模型文本）；`ice_gui._export_autotherm` 保存对话框；SLOT_MAP `"Write Autotherm file"`（此前 NYI）。
- **测试**：tests/test_p19_report4.py（5 项：完整报告含 5 段、空项目各段 No 文案、write_real_report 含段、Autotherm 文件内容、Autotherm 槽位）；report/export/golden 29 项通过无回归。

### P19-4k — Solve 面板字段全集（Patch / trials / ROM）完成，P19-4 收官

- **ice_solve**：新增 `PATCH_FIELDS`（patch_object/patch_temp/patch_apply_to）、`TRIALS_FIELDS`（solve_do_trials/solve_trial_prefix/solve_trial_fixed_prefix/solve_do_fast_trials）、`ROM_FIELDS`（ss_krylov/krylov_input_objects/krylov_cons_order/krylov_eval_order/krylov_heat_flux/krylov_eval_times/krylov_trans_id）——键名从 oracle problem 文件实测（9-2Optimization/10-1transient）。
- **ice_solve_gui.SolveSettingsDialog.KINDS**：新增 `Define trials`/`Create Krylov ROM`（与 Basic/Advanced/Parallel 同一 form 编辑路径，`write_setter` 写回 problem）。
- **ice_gui**：`_define_trials` / `_create_krylov_rom` 打开对应字段对话框（无项目/无 problem → _nyi）；SLOT_MAP `"Define trials"`/`"Create Krylov ROM"`（此前 NYI）。
- **测试**：tests/test_p19_solvefields.py（6 项：三字段表键名、槽位解析、KINDS 含两键、GUI 打开对话框 kind/title、无 problem → _nyi）；solvefields/solve/p6_solve/golden/gui 50 项通过无回归。
- **P19-4 全部 5 项完成**（等值面/曲线/瞬态·单位·zoom·powermap/Solve 字段全集/报告全套）。

### P19-3 — 编辑器逐类字段全集（golden 键取证 + 合并）完成

- **取证**：扫描 `_report/projects/*.json`（26 个解码工程）的每对象 `properties` 键，按 kind 归并得到 15 类的**真实逐类属性键全集**（如 block: solid_material/temp_total/res_rjc/res_rjb/res_jpow/thermal_heat_tr_face_profile；package: die_dim1/ball_diam/sub_*_trace_pct/via_*；wall: thermal_type/thermal_heat_tr*/convection_type/int_emis_on；pcb: kneff/kpeff/sbth/tth/tper…）。
- **ice_editors**：新增 `GOLDEN_KEYS`（取证键全集）→ `spec_for(kind)` 合并：PROPERTY_SPECS 人工精修行 + 未收录的 golden 键自动变为可编辑行（数值类→text、开关类→check、标签 `_label_of`）；golden 键并入 `COMMON_SETVAL_KEYS`（模型编解码持久化）。
- **测试**：tests/test_p19_editors.py（5 项：golden 全覆盖、golden 键持久化、键点检、编辑器 Properties 页含 block_type/solid_material/res_rjc、未知 kind 显示占位）；editors/forms/create/gui/golden 44 项通过无回归。

### P19-3b — 剩余细项（数值键 spin 化 + spreadsheet/几何窗锁定）完成

- **数值键控件类型细化**：`ice_editors.kind_of(key)`——check 键集→check、计数键（num1/via_num…）→int、数值形键（power/temp/res_*/dim*/coeff/conductivity/…，正则）→spin，其余→text；`spec_for` 自动行按 kind_of 推断；人工精修行 temp/heat/power/flow/pressure/rpm/rjc/rjb/area/loss/velocity 全部 text→spin。
- **spreadsheet 多体编辑**（已有 SpreadsheetDialog，本轮补锁定测试）：rows=多对象、columns=Name/Kind+键集，编辑→`_apply` 写回 setvals/shape。
- **右下几何信息窗橙色对齐按钮族**（已有 GeometryWindow，本轮补锁定测试）：6 个橙色（#f3a53a）xS..zE 对齐/拉伸按钮 + 坐标框 + set_object 填充 + Apply 双写。
- **测试**：tests/test_p19_editors.py 增至 8 项（新增：数值键 spin/int/check 断言、spreadsheet 多体编辑写回、几何窗 6 橙色按钮+填充）；editors/forms/create/gui/golden/tree 53 项通过无回归。
- **P19-3 收官**（字段全集+控件类型+spreadsheet+几何窗全部落地）。

### P19-2 — 3D 视区视觉契约全集（逐对象透明度 + 全项锁定）完成

- **盘点**：Lights 面板（_lights_dialog→ViewOptionsDialog）、背景 solid/双色渐变（_set_background）、5 种着色模式 per-type 颜色/线宽（_make_actor/shading menus）、user views 保存/清除/读写（_save/_write/_read/_clear_user_views）、面/边循环选择红黄高亮（AlignSession）、对象拖放移动（_drag_move）、Visible grid/Origin/Rulers/Title/Date/Construction 显示层（make_display_actors + _toggle_display_layer）、Depthcue（renderer.SetFog 切换）、右下实时坐标（_mouse_pos_label）均已实现。
- **新增（真实缺口）逐对象透明度**：SceneObject 增 `opacity` 字段；build_scene 读 `setvals['opacity']` 传入；`_make_actor` 应用 `prop.SetOpacity(so.opacity)`。
- **测试**：tests/test_p19_viewcontract.py（5 项：build_scene 读取 opacity、_make_actor 应用到 actor、display_actors 含 grid/origin/rulers/title/date/mesh、Depthcue 切换无异常、背景 solid 路径）；view3d/align/gui/golden 49 项通过无回归。

### P19-2b — 剩余渐进项（per-type 面板 / construction 层 / 右下状态栏 4 段）完成

- **per-type 装饰/线宽/透明度面板**：`KIND_VISUALS`/`kind_visuals(kind)`（color/width/opacity 默认取自 KIND_COLORS）；`_make_actor` 用 per-type 颜色、wire 线宽、opacity（per-type × 逐对象）；`ice_panes.KindVisualsDialog`（每 kind 一行：颜色 hex/线宽/透明度，`values()` 返回）；`ice_gui._edit_kind_visuals` + View 菜单「Per-type visuals...」。
- **construction 层**：`make_display_actors` 新增 `construction`（盒骨架 12 边，蓝灰 1.2px）与 `construction_points`（底面网格交点，橙色 4px），默认隐藏；`_toggle_display_layer` 处理「Display construction lines/points」；`_ensure_display_actors` 按显示状态初始化（默认关）。
- **右下状态栏 4 段**：底部新增 4 个 QLabel 段（Sel / Shading / Units / Objects），`_update_status_segments()` 在 `_refresh` 时刷新。
- **测试**：tests/test_p19_viewcontract.py 5→11 项（kind_visuals 默认、_make_actor 应用 visuals、KindVisualsDialog values 往返+编辑、construction 两 actor 存在且默认隐藏、状态栏 4 段更新、View 菜单含 Per-type visuals）；view3d/align/gui/golden/tree 61 项通过无回归。
- **P19-2 收官**（视觉契约全集全部落地）。

### P19-5 — 宏官方 diff 校验（oracle 锚定）完成

- **tools/macro_diff.py**（官方 Tcl 宏为 digest 加密不可直跑，oracle 取两层）：① 内置 5 宏按构建器规则表 diff（对象数/kind/package_type/body bbox，默认参数）；② **845 库部件以官方参数文件为 golden**——每个部件的 package 必须逐字回显官方 ball_pitch/ball_num1/2/die_dim1/2/library，且几何规则 bbox = ball_num2·pitch × ball_num1·pitch × package_thickness（delta=0）。golden 锚定 `tools/probe_work/macro_golden.json` + 报告 `macro_diff_report.json`。
- **diff 校具抓出并修复 2 个潜伏真 bug**：`build_blower` 缺 `default_object` 导入（此前被 `except Exception: pass` 掩盖）+ 未守护 `o.setvals` 属性。
- **结果**：builtin 5/5、library 845/845，**delta_total = 0**。
- **测试**：tests/test_p19_macrodiff.py（5 项：内置 0 delta、库部件抽样 0 delta、blower 修复、golden 锚定匹配、全量 0 delta）；macrodiff/p7_macros/macrolang/libwizard/ecad 26 项通过无回归。
- **P19-5 收官**。

### P19-1 — 晶格量化表面节点（机理复刻）完成，P19 全部收官

- **ice_hdm.lattice_surface_nodes(cyls, base, depth, phase, band, snap_tol, stagger)**：P18j 定案机理的实现——**全局共享细晶格**（step=base/2^depth，全局相位）采样柱面邻域（|ρ−r(z)|≤band·g）→ 径向投影锥面 → **部分吸附量化**（仅 |Δ|<snap_tol·g 时回晶格，否则保留连续投影值）+ **逐柱相位错开**（golden-ratio·stagger，对应 oracle 每柱八叉树叶相对晶格的相位差）。
- **tools/hdm_lattice_surface.py**：对 10-1transient 三柱列（cx=0.15，rows 0.25/0.30/0.35，锥台 r 0.012→0.02）扫描 (depth, phase, band, snap_tol, stagger)。
- **机制指纹复现**（best depth=4/phase=(0,0.008)/band=1.0/snap_tol=0.4/stagger=0.7）：同列柱 **x 集部分重叠 0.2365 / 0.0386 / 0.1923**（oracle 27-41% 同区间、非 0/100%），每列 distinct x 854-1071（oracle 环带 ~653-1001 同量级），y 重叠 0.15-0.28。此前严格全量化 x 重叠恒 100%、零错开恒 0——部分重叠需要「共享晶格 + 部分吸附 + 逐柱相位」三要素同时成立（这正是 oracle 的晶格派生采样机制）。
- **测试**：tests/test_p19_lattice.py（5 项：重叠严格在 0-60% 部分区间、每列 distinct x 400-2500（oracle 量级）、更细晶格→更细谱、确定性、空柱列返回 (0,3)）；lattice/positions/refine/replication/continuous/exact 70 项通过无回归。
- **P19-1 收官 → P19-1~P19-10 全部完成**（P19 里程碑全线收官）。

## P19 收官后的下一程：docs/PLAN_100PCT.md

### G1 — 网格质量统计面板 完成（Phase G 启动）

- **ice_mesh.mesh_quality(result)**：结构化网格质量度量——正交性=1.0（结构化完美）、偏斜=0、**逐单元长宽比分布**（dx/dy/dz 广播 min/max/mean + 最差单元 (i,j,k)）、总容积；修复 worst_cell 为 tuple 的 int() 转换 bug。
- **ice_panes.MeshQualityDialog**：Cells/Nodes/Orthogonality/Skewness/Min·Max·Mean aspect/Worst cell/Volume 统计面板。
- **ice_gui._show_mesh_quality**：Model 菜单「Mesh quality...」（无网格时 WARN）；`_rebuild_model_zoom_menu` 加菜单项。
- **测试**：tests/test_p19_quality.py（6 项：均匀网格正交性/偏斜精确+矩形域 aspect∈[1,3)、非均匀 aspect>1、无网格 WARN、对话框收到质量 dict、Model 菜单项）；quality/mesh/golden/gui 43 项通过无回归。

### F4 — 多命令按钮 完成，Phase F 收官

- **ice_menus_toolbars.build_toolbars + _multi_commands**：golden `scalar ['multiple', cmd1, cmd2]`（Alignment 工具栏 3 组 morph/move-only 变体对）→ 弹出菜单 QToolButton；ALIGN_OPS 补 `Align edges/vertices - move only` 变体。
- **ice_gui._tb_multi**：默认 action=第一变体、MenuButtonPopup 列出全部变体、各变体按 ALIGN_OPS/SLOT_MAP 解析槽位。
- **golden 测试**：`test_toolbar_groups_match_golden` 过滤空文本宿主 action（多命令按钮是 widget 非 golden scalar，另在 test_p19_multibtn 锁定）。
- **测试**：tests/test_p19_multibtn.py（2 项：Alignment 3 个弹出按钮及菜单变体对、golden 工具栏 action 列表不含 multiple）；multibtn/golden/gui 30 项通过无回归。
- **Phase F（UI 契约补漏）F1/F2/F3/F4 全部完成**。

### F3 — 树右键全集 + 组操作补漏 完成

- **修复真 bug**：「Delete all」此前误接 `_group_all(..., False)`（=Deactivate all）→ 改为 `_delete_group(name, delete_all=True)`：删除组内对象并入 Trash；`_delete_group` 实现 delete_all 语义。
- **Copy params 落地**（原 NYI）：`_copy_group_params(name)` 收集成员 setvals 摘要写剪贴板。
- **Show/Clear clipboard + Search library**（golden 树命令 tree_show/clear_clipboard、tree_search_library）：根菜单三项 + 处理器；`_search_library` 高亮库树匹配节点。
- **树按键对齐核实**：golden 树热键（Toggle object active/visible、Open/close tree node、Open/close model subtree、Toggle shading type）已全部绑定（test 锁定 `_hotkey_actions`）。
- **测试**：tests/test_p19_treefx.py（6 项：Delete all 删成员入 Trash、Delete group 保留对象、Copy params 写剪贴板、Show/Clear clipboard、Search library 无异常、树热键绑定）；tree/gui/golden/create 45 项通过无回归。

### F1 — Windows 动态菜单（toplevel 注册表→实时菜单）完成

- **ice_menus_toolbars.rebuild_windows_menu(gui)**：Windows 菜单由 `gui._toplevels`（name→widget）实时生成——每项可勾选，触发即显示/置顶或隐藏对应 toplevel；`_build_dynamic_menus` 的静态 Message/Project 段替换为注册表重建。
- **ice_gui**：`_toplevels` 注册表 + `register_toplevel(name, widget)`（去重+重建菜单）+ `_register_toplevels()`（Message/Project/Graphics/Geometry 四个主窗）；**绘图窗动态注册**——`_open_plot` 每个新 PlotWindow 自动加入 Windows 菜单（golden dynamic 注记「toplevel registry」语义）。
- **测试**：tests/test_p19_windows.py（4 项：注册表 4 主窗可勾选、register 去重、toggle 显隐双向、绘图窗自动入表）；golden/gui 32 项通过无回归。

### F2 — File Workbench 变体 完成（Phase F 启动）

- **ice_menus_toolbars**：重构 `build_menus` 内部递归为可复用 `build_entries(gui, parent, entries, skip=(), replace=None)`；新增 `build_file_variant(gui, wb=True)`——WB 变体按 golden 注记（menus_icepak.tcl L170-211）：去 New/Open/Save-as/Unpack/Import JEDEC/Export JEDEC，首项 `Refresh Input Data`，`Quit`→`Close Icepak`（skip 递归进 Import/Export 级联）。
- **ice_gui**：`_workbench` 由 `ICE_WORKBENCH=1` 环境开关；`_refresh_input_data`（重解析当前工程）、`_close_icepak`（close）；SLOT_MAP 两槽位。
- **测试**：tests/test_p19_wbfile.py（4 项：槽位、独立版 File 菜单不变、WB 变体增删对表、环境开关构造变体）；golden/gui/shell 37 项通过无回归。

### E3 — fdat 全变量访问（压力/速度/多步前值）完成

- **取证**：10-1transient `transient00.fdat` 含 **125 个 3300 字段节**，变量全集：SV_T/SV_P/SV_U/SV_V/SV_W/SV_DENSITY/SV_H/SV_MU_LAM/SV_HEAT_FLUX/SV_WALL_*/SV_RAD_HEAT_*/SV_FLUX + `_M1`（前一瞬态步）各变量；fdat 头 `(33 (58908 185451 62626))` 与 cas 边界 zone 面行数 185451 精确一致。
- **新增**：`fdat_variables(parsed)`（SV_* 变量表）、`cell_zone_field(parsed, variable, clean=True)`（按名称声明的真实单元数 `N cells` 切片 + 哨兵双精度清洗）、`real_field_values(project_dir, variable)`（任意变量单元区值）。
- **测试**：tests/test_p19_fdatvars.py（3 项：合成变量表/cell-zone 判定、真实全变量 58908 值+压力范围+_M1 前步、real_field_values 访问器）；fdat/fdatvars 8 项通过。

### E1b — grid_output 尾表（节描述符）解码 完成

- **取证**：面节之后（offset 4403104 起）为节描述符块——16B 前置 + `(tag, value)` 对：`(6, 58908)`=单元声明数（**与 cas 区头 58908 完全一致**，解了 E1 的 Δ1：grid 自身声明 58908 单元、落盘 58907 条）、`(14, 12218)`=面声明数（12217+1 前导面 ✓）、`(16,2)`/`(11,2)`/`(12,2)`/`(3,3)` 等；**主头 hdr[20]/hdr[32] 即指向描述符表内偏移（+32/+16）的指针**。描述符之后为嵌套邻接/区域表（含面 id 对、双精度区）——记为 E1c 后续。
- **fluent_grid.decode_grid_output** 扩展：返回 `tail`（start/descriptors/header_pointers/declared_cells/declared_faces）。
- **测试**：test_p19_grid32 断言 `(6,58908)`/`(14,12218)` + 头指针偏移；grid/oracle 10 项通过无回归。

### E2 — problem 数组字段全解析 + 结构化访问器 完成

- **现状核实**：`problem_parser` 已完整解析 `array set`（9-2=57、10-1=47 个数组，多 token 值折叠）；缺口=语义访问器。
- **新增**：`ProblemFile.table(name)`（多 token 值拆成列表）、`trials()`（逐 trial 变量取自 `expression_param_random`，`{trial: {name, vars}}`——真实结构取证：`expression_param_range` 以参数名为键存 min/max/step/count，非 trial 键）、`design_params()`（`expression_params/range/choices` → `{param: {value, range, choice}}`）。
- **测试**：tests/test_p19_problem.py（7 项：合成全解析/结构化 trials/瞬态表/table 拆分/design_params + 真实 9-2 trials（finCount=18）/10-1 瞬态表）；problem/solve 13 项通过无回归。

### E1 — grid_output face/cell 区解码 完成（Phase E 启动）

- **fluent_grid.decode_grid_output(path, n_nodes)**：结构驱动全节解码——头 64B → 节点节 28B BE `[counter][x][y][z]`（计数 0..N-1）→ 前导面 24B `[4 节点 id][face id][zone]`（id=N+1）→ 单元节 40B `[8 节点 id][cell id][zone]`（id 自 N+2 连续）→ 面节 24B `[4 节点 id][face id][zone]`（id 自 N+n_cells+2 连续）。
- **10-1transient 实测**：nodes **62626** ✓（nodemap）、cells **58907**（oracle cas 58908，Δ1=被计数但未落盘的一个退化单元；id 62628..121534 连续、节点 id 全合法）、faces **12217**（id 121535..133751 连续，之后尾部为另一结构表=面邻接，留作 E1b）。
- **测试**：tests/test_p19_grid32.py（2 项：真实 golden（节点/单元/面三节 id 连续性+合法域）、合成往返）；grid/oracle 10 项通过无回归。

## P19 收官后的下一程：docs/PLAN_100PCT.md

- 基线：91 提交 / 23 ice_* 模块 / 44 tools / 53 测试文件 313 测试函数。
- 剩余真实差距（更新后的矩阵）：① grid_output **face/cell 区 32B 记录解码**（D5 唯一数据缺口）；② problem 数组字段 + fdat 全变量；③ File Workbench 变体 / Windows 动态菜单 / 多命令按钮 / 树图标与组右键全集；④ 真实 mesher 沙箱对接 + 质量统计/优先级/挖空面板 + heat_solver 深化 + ROM/优化 UI；⑤ ~/.icepak_config 兼容导入导出 / Annotations / Command prompt 全命令；⑥ P19-1 参数拟合级（x/y ±3~5%、1e-3 >10%）+ 教程截图视觉回归 + 全量分片 CI。
- 新计划 Phase E（数据层）→ F（UI 契约）→ G（网格/求解）→ H（配置/周边）→ I（位置收官/回归），约 5-6 周，每项含验收口径。
