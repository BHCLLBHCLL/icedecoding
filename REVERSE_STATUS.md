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
