# 对标 100% 新开发计划（PLAN_100PCT）

> 生成时间：P19-1~P19-10 全部收官后。基线：91 次提交、23 个 ice_* 模块、
> 44 个 tools 脚本、53 个测试文件 313 个测试函数、全套（分片）通过。

## 一、现状总览（更新后的深度矩阵）

| 子系统 | 深度 | 剩余差距（100% 对标口径） |
| --- | --- | --- |
| model 解码 / 编码 | D5 | model 编码已字节级往返（Phase B）✅ |
| problem | D3 | **数组类字段**（gradient/transient 表）全解析 |
| grid_params | D4 | ✅（oracle 交叉验证） |
| grid_output 二进制 | D5 | **face/cell 区（32B 记录）完整解码**——D5 层唯一数据缺口 |
| cas/fdat/resd | D3 | fdat 全变量（压力/速度/残差历史全字段）补全 |
| 菜单/工具栏/热键 | D4 | Windows 动态菜单；**File Workbench 变体**；多命令按钮 |
| 主窗口/树 | D3 | 树图标按键对齐；组右键全集 |
| 3D 视区 | D3/D4 | P19-2 已收官 ✅（剩余仅教程截图级回归） |
| 对象编辑器 | D3 | P19-3 已收官 ✅（剩余 spreadsheet 单元格类型化） |
| 网格 | D4 | **真实 mesher 沙箱对接**；质量统计面板；优先级/挖空面板 |
| 求解 | D3 | 自研 heat_solver 深化（对流/辐射）；**ROM/优化 UI + solution ID 管理** |
| 后处理 | D3/D4 | P19-4 已收官 ✅ |
| 报告 | D3 | P19-4j 已收官 ✅（剩余 5 导出已在 D6d ✅） |
| 宏 | D4 | P19-5 已收官 ✅ |
| ECAD | D4 | ✅（ECAD 收官） |
| 偏好/语言 | D3 | **~/.icepak_config 变量级兼容导入导出**；**Annotations** |
| 周边 | D3 | **Command prompt 全命令**；Python console 等价；图像导出格式补全 |
| HDM 位置复刻 | D4 | P19-1 机制已复刻 ✅（剩余**参数拟合级**：x/y ±3~5%、1e-3 重合 >10%） |

## 二、新开发计划（Phase E → I）

### Phase E — 数据层收尾（D5 唯一缺口 + problem/fdat 补全）
- **E1 grid_output face/cell 区解码** ✅ + **E1b 尾表描述符** ✅：`decode_grid_output` 全节解码 + tail 描述符表（`(6,58908)` 单元声明数=cas 精确值、`(14,12218)` 面声明数、主头指针指向描述符）；cells 落盘 58907（声明 58908 Δ1）、faces 12217。剩余 E1c：描述符后嵌套邻接/区域表。
- **E2 problem 数组字段** ✅：`array set` 已全解析（9-2=57/10-1=47 数组）+ 新增结构化访问器 `table()/trials()/design_params()`（真实结构取证：逐 trial 变量在 expression_param_random、range 以参数名为键）。验收：26 工程零未知键。
- **E3 fdat 全变量** ✅：`fdat_variables` / `cell_zone_field`（真实单元数切片+哨兵清洗）/ `real_field_values`；10-1 实测 125 节全变量（SV_T/P/U/V/W/DENSITY/H/HEAT_FLUX/WALL_* + `_M1` 前步）、头三元组与 cas 面数 185451 精确一致。
- **E3 fdat 全变量**：压力/速度/多瞬态步全字段（现仅 SV_T 为主）。
  验收：12-1/10-1 全变量可加载；后处理按变量选择。

### Phase F — UI 契约补漏（菜单/树/多命令）
- **F1 Windows 动态菜单** ✅：`rebuild_windows_menu`——toplevel 注册表（Message/Project/Graphics/Geometry + 每个 PlotWindow 动态入表）实时生成可勾选显隐菜单（golden dynamic 注记语义）。
- **F2 File Workbench 变体** ✅：`build_file_variant(gui, wb=True)`——golden 注记 WB 变体（Refresh Input Data 首项、Close Icepak 替 Quit、去 New/Open/Save-as/Unpack/JEDEC 导入导出），`ICE_WORKBENCH=1` 环境开关。
- **F3 树图标/按键对齐 + 组右键全集** ✅：修复 Delete all 误接 bug（delete_all 语义）、Copy params 落地（原 NYI）、Show/Clear clipboard + Search library 入根菜单、golden 树热键绑定锁定。
- **F4 多命令按钮** ✅：golden `['multiple', A, B]` → MenuButtonPopup QToolButton（默认 A、弹出全变体），ALIGN_OPS 补全变体。
  验收：golden UI 测试 1:1（菜单/工具栏/热键/树命令全对表）——**Phase F 收官**。

### Phase G — 网格/求解深水区
- **G1 真实 mesher 沙箱对接**：mesher.exe 在 dev 沙箱跑样例 → 质量统计面板（正交性/长宽比/偏斜）数据源。
- **G2 优先级/挖空面板**：Edit priorities / Edit cutouts 面板接线到 grid_params。
- **G3 heat_solver 深化**：对流/辐射项 + oracle 温度比对（D2→D3）。
- **G4 ROM/优化 UI + solution ID 管理**：ROM_FIELDS 已有，补优化面板与 solution id 切换。
  验收：G1 质量指标与 mesher oracle 输出一致；G3 温度 vs oracle 偏差 <5%。

### Phase H — 配置/周边
- **H1 ~/.icepak_config 变量级兼容导入导出**（ice_prefs 全变量）。
- **H2 Annotations**（注释对象创建/显示）。
- **H3 Command prompt 全命令 + Python console 等价**（ice_cli 扩展全 golden 命令）。
- **H4 图像导出格式补全**（已有 Create image file 路径）。
  验收：H1 配置文件与 Icepak 同变量互读；H3 全命令经 CLI 回放。

### Phase I — 位置复刻收官 + 视觉回归 + CI
- **I1 P19-1 参数拟合**：在 lattice_surface_nodes 三要素上拟合 x/y ±3~5%、比值 1.15-1.25、1e-3 重合 >10%；golden 化 10-1 指标。
- **I2 教程截图视觉回归**：_report/screenshots 对照（图 3-31/3-62/3-65 等）。
- **I3 全量分片 CI**：把 20 分钟易中断的全量套件按模块分片（mesh/post/ecad/gui/…），每片独立可跑、内存友好。
  验收：I1 双指标达标入 golden；I3 CI 分片全绿。

## 三、排期估计
- Phase E（数据层）：~1 周（E1 取证最硬）
- Phase F（UI 契约）：~1 周
- Phase G（网格/求解）：~1.5-2 周（G1/G3 深）
- Phase H（配置/周边）：~0.5-1 周
- Phase I（收官/回归）：~1 周（I1 参数拟合为研究项）
- 合计 ~5-6 周
