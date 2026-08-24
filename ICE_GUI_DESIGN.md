# ice_gui 详细设计（100% 对标 ANSYS Icepak 2019 R3 主界面）

> 日期：2026-08-24
> 仓库：`icedecoding`
> 对照源：本机安装 `C:\Program Files\ANSYS Inc\v195\Icepak`
> 启动器：`C:\Program Files\ANSYS Inc\v195\Icepak\bin\icepak19.5win64.bat`
>   → `icepak19.5\bin.win64_amd\icepak.exe`
> 技术路线：对齐 `D:\training\cgns\cabdecoding`（`CAB_GUI_DESIGN.md` + `cab_gui.py` / `cab_panes.py` / `cab_icons.py`）
>
> **权威 UI 定义（已逆向遍历，非猜测）：**
>
> | 来源 | 路径 | 覆盖 |
> |------|------|------|
> | 菜单 + 水平工具栏 | `lib/icepak/menus_icepak.tcl` | File/Edit/View/Orient/Macros/Model/Solve/Post/Report/Windows/Help 全量 + 8 组工具栏 |
> | 命令绑定 / 图标名 | `lib/icepak/commands_icepak.tcl` | 每条菜单的 Tcl 命令、工具栏图标 id |
> | 通用命令 | `lib/autohex/commands_autohex.tcl` | New/Open/Quit、着色、对齐、树操作、CAD |
> | 视口命令 | `lib/guibase/commands_guibase.tcl` | Home/Zoom/Orient/Display 开关 |
> | 启动 / Welcome | `lib/autohex/autohex.tcl` | `ice_dialog` Existing/New/Unpack/Quit |
> | 树节点中英对照 | `lib/icepak/language_text_icepak_Chinese.tcl` | Problem setup / Model / Trash… |
> | 版本与布局开关 | `lib/icepak/init_icepak.tcl` | `tree_on_left`、`tree_has_libraries`、`version_p=2019 R3` |
> | 3D 光标 / Logo | `lib/tdv/*.cur` `*.ppm` | 拾取/旋转/平移/缩放 + ANSYS 水印 |
> | 帮助锚点 | `lib/icepak/language_text_icepak_English.tcl` | `ice_ug_sec_*` → `commonfiles/help/en-us/help/ice_ug` |
> | 实机截图 | 用户提供的 Icepak 主界面 | 分区、Welcome、消息栏 Verbose/Log/Save |

Icepak 本体是 **Tk 8.5 + BWidget + TDV OpenGL 视口**（ICEM 系 `guibase`），不是 Qt。本仓库用 **PyQt5 + VTK** 做同构复刻（与 cabdecoding 复刻 STpre 相同策略）：菜单/工具栏/树/视口/消息栏 **视觉与命令名 100% 对齐**，求解器/网格器/许可相关功能标记 NYI。

---

## 1. 设计目标与边界

### 1.1 目标

把当前 `ice_gui.py`（简易「左树 + 右 3D/属性 + 底日志」查看器）升级为 **Icepak 2019 R3 主窗口同构** 的项目查看/轻量编辑器。

| 能力 | 目标 |
|------|------|
| 冷启动 | Welcome 四按钮：Existing / New / Unpack / Quit |
| 打开 / 保存 | 对齐 `[File]`：New / Open / Save / Save as / Pack / Unpack `.tzr` |
| 模型浏览 | 左栏 **Project / Library** 双页树，节点与 Icepak 完全同名同序 |
| 3D 绘制 | 浅蓝竖向渐变、左下 XYZ 三联、右上 `ANSYS 2019 R3` 水印、五种着色 |
| 菜单 | 11 个顶栏：**全量骨架 + 分级启用**（名称/快捷键/级联与 Tcl 一致） |
| 工具栏 | 顶栏 2–3 行分组图标 + 视口左侧 TDV 竖条 |
| 日志 | 底栏 Message：文本 + `Verbose` / `Log` / `Save` |
| 导出 | 已有 JSON/CSV 管线挂到 File→Export 子集 |

### 1.2 明确不做（菜单保留入口，标记 NYI）

Fluent/Icepak 求解器启动、网格生成交互、辐射角系数计算、优化/Krylov ROM、EM Mapping、IDF/IDX/ECXML 全量导入、宏脚本真实执行、材料库写入。  
触发后写入 Message：`[name] not available in ice viewer (Icepak-only / not yet mapped).` —— 与 `cab_gui._nyi` / `pph_gui._nyi` 一致。

### 1.3 与 cabdecoding 的对应关系

| cabdecoding (STpre) | icedecoding (Icepak) |
|---------------------|----------------------|
| `CabViewer(QMainWindow)` | `IceGui(QMainWindow)`（保留类名，改布局） |
| 8 菜单：File Edit View Part Wizard Mesh Option Help | **11 菜单**：File Edit View Orient Macros Model Solve Post Report Windows Help |
| 左：Tree/List + Control | 左：**Project/Library 树**（无独立 Control 窗；属性用对象编辑对话框） |
| 中：Draw Window | 中：**Graphics / TDV 视口** |
| 底：Message | 底：**Message** + Verbose/Log/Save |
| `AppIcons` 矢量 22px | `IceIcons`：优先复刻 Icepak PNG/XBM 外形，缺失则矢量绘制 |
| `_nyi` + Message 日志 | 同范式 |
| 离屏 `enable_3d=False` | 已有，保留并扩展菜单断言 |

---

## 2. 现状差距（当前 `ice_gui.py`）

| 已有 | 缺失（本设计补齐） |
|------|-------------------|
| 单列项目/对象树 | Icepak 双页树：Project 固定节点 + Library |
| 单行文字工具栏 | 8 组图标工具栏 + 左竖条 |
| 菜单仅 文件/视图 | 11 顶栏全量 + 级联 |
| VTK 灰蓝渐变 + 线框/半透明 | 五种着色、ANSYS 水印、Home/Orient 轴视图、1/4 分屏 |
| 无 Welcome | Existing/New/Unpack/Quit 模态 |
| 纯文本 Message | Verbose/Log/Save 控件条 |
| 无对象创建入口 | Object creation 工具栏 18 类图元 |
| 属性嵌在 3D 下方 | Icepak 风格：双击树节点弹出 Edit 对话框（一期可用现有 DetailsTable 作为对话框体） |

---

## 3. 总体布局规格

### 3.1 主窗口分区（对标截图 + `init_icepak.tcl`）

Icepak 开关：`tree_on_left 1`、`tree_has_libraries 1`、`mainwindow_menubar 1`、`ICEPAK_ONE_WINDOW 1`、`allow_multiple_views 1`、`no_menu_tearoff 1`。

```
┌─ Menu: File  Edit  View  Orient  Macros  Model  Solve  Post  Report  Windows  Help ─┐
├─ Toolbar row 1: [File] [Edit] [Viewing] [Orientation] ────────────────────────────────┤
├─ Toolbar row 2: [Model and solve] [Postprocessing] ───────────────────────────────────┤
├─ Toolbar row 3 (object_tools): [Object creation] [Object modification] [Alignment] ───┤
├────────────┬──┬───────────────────────────────────────────────────────────────────────┤
│ Project │ │ │                                                                       │
│ Library │V│ │                     Graphics Window (TDV)                             │
│         │e│ │   浅蓝→白竖向渐变                                                       │
│ tree    │r│ │   右上: ANSYS 2019 R3                                                   │
│         │t│ │   左下: X红 Y绿 Z蓝 三联                                                 │
│         │ │ │   冷启动: Welcome to Icepak 模态                                        │
├────────────┴──┴───────────────────────────────────────────────────────────────────────┤
│ Message  （只读文本）                                                                 │
│ [x] Verbose   [x] Log   [Save]                                                        │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

- 类名：`IceGui(QMainWindow)`（保留）
- 标题：冷启动 `ANSYS Icepak 2019 R3`；打开后 `ANSYS Icepak 2019 R3 — {project}`
- 默认尺寸：`1280×800` 起，推荐 `1600×900`
- 中央：**水平 `QSplitter`**
  - 左：`QTabWidget`（Project / Library）最小宽 220，默认 260
  - 中：左竖条（固定宽 28–32）+ Graphics
  - 不可把属性表永久钉在 3D 下方（那是当前查看器布局，不是 Icepak）
- 底：垂直 splitter 把 Graphics | Message 切开，比例约 **5:1**，Message 默认高 140
- 拉伸因子：`main=[0,0,1]`（树、竖条不伸，视口伸）

### 3.2 视觉（对标截图）

| 项 | 规格 |
|----|------|
| 菜单栏/工具栏底 | 系统灰 `#e8e8e8`–`#d4d0c8`（经典 Win/Tk） |
| 工具栏图标 | 24×24 彩色多色，**无文字**（Icepak 为 icon-only；cab 用 TextUnderIcon，这里不要照搬） |
| Graphics 背景 | 竖向渐变：上 `#9ec8e8` → 下 `#f4f7fb`（截图浅蓝到白） |
| 坐标三联 | 视口左下，X=`#cc0000` Y=`#00aa00` Z=`#2244cc`，`vtkOrientationMarkerWidget` |
| 水印 | 视口右上 `ANSYS 2019 R3`，浅色半透明 |
| 选中高亮 | Icepak `selectbg_color #99d9ea` |
| Message | 白底、系统默认比例字体（Icepak 非等宽为主；日志可用 Consolas 9） |
| 分割条 | 细灰边框，可拖 |

### 3.3 模块拆分

| 文件 | 职责 |
|------|------|
| `ice_gui.py` | `IceGui`：菜单/工具栏/布局/信号总线/Welcome |
| `ice_icons.py` | `IceIcons`（移植 cab `AppIcons` 画法，Icepak 图标名） |
| `ice_panes.py` | `ProjectTree`、`LibraryTree`、`MessageWindow`、`TdvStrip`、`WelcomeDialog` |
| `ice_view3d.py` | Graphics：VTK 封装、着色、Orient、拾取、水印 |
| `ice_actions.py` | Action 表（id → slot / NYI），菜单与工具栏共享 |
| `ice_edit_dialogs.py` | 对象 Edit 对话框（二期；一期可用 `DetailsTable` 对话框） |

短期可先落在 `ice_gui.py` + `ice_panes.py`；超过 ~2k 行再拆（cab 同策略）。

---

## 4. 冷启动 Welcome

源：`autohex.tcl` → `ice_dialog .new_job "Welcome to Icepak"`。

文案（英文，与安装版一致）：

> **Welcome to Icepak**
>
> Do you want to open an existing project, create a new one, or unpack a .tzr file?

四个大按钮（图标来自 `new.png` / `existing.png` / `unpack.png` / `quit.png`）：

| 按钮 | 行为 |
|------|------|
| Existing | `File → Open project`（目录选择；识别含 `model` 的 Icepak 工程） |
| New | `File → New project`（空 cabinet/domain；一期可建空工程骨架） |
| Unpack | `File → Unpack project`（`.tzr` / `.tgz` / `.tar` / `.gz`） |
| Quit | 退出 |

命令行已给路径时 **跳过** Welcome（对齐 `tool_setup`：`initial_job` 存在则直接 `job_load`）。

---

## 5. 菜单设计（对齐 `menus_icepak.tcl`，独立模式 `from_Workbench==0`）

实现策略：**全量菜单骨架 + 分级启用**。  
图例：✅ 应对齐实现　◐ 部分（查看器能力）　⬜ NYI（记日志）

快捷键来源：`command_set_hotkeys` + `command_set_hotkeys_tdv`（同一文件）。

### 5.1 File(&F)　keyboard `f`

| 项 | 快捷键 | 状态 | 行为 |
|----|--------|------|------|
| New project | Ctrl+N | ◐ | 空工程 + 默认 cabinet |
| Open project | Ctrl+O | ✅ | 打开项目目录 |
| Merge project | | ⬜ | |
| Reload main version | Ctrl+L | ✅ | 重新载入当前工程 |
| — | | | |
| Save project | Ctrl+S | ◐ | 一期：导出/写回只读提示；二期写 model |
| Save project as | | ◐ | |
| — | | | |
| Import ▶ CSV/Excel | | ⬜ | |
| Import ▶ IDF file ▶ New board / Update board | | ⬜ | |
| Import ▶ IDX file | | ⬜ | |
| Import ▶ Electronics Cooling XML | | ⬜ | |
| Import ▶ Powermaps ▶ Apache Sentinel TI / Cadence tab / Cadence Stacked Die / Gradient Firebolt i2p / RedHawk CTM | | ⬜ | |
| Import ▶ Networks | | ⬜ | |
| Import ▶ JEDEC PTD/JEP30 file | | ⬜ | |
| Export ▶ ANSYS Electronics Desktop script | | ⬜ | |
| Export ▶ CSV/Excel | | ◐ | 挂现有 `export.py` |
| Export ▶ IDF / EC XML / Networks / JEDEC PTD/JEP30 | | ⬜ | |
| EM Mapping ▶ Volumetric / Surface heat losses | | ⬜ | |
| — | | | |
| Unpack project | | ✅ | `.tzr` |
| Pack project | | ◐ | 打 `.tzr`（gzip+tar，已有 `tzr.py` 逆向） |
| — | | | |
| Cleanup | | ⬜ | |
| Print screen | Ctrl+P | ◐ | 视口截图打印 |
| Create image file | | ◐ | 视口存 PNG |
| Command prompt | | ◐ | 打开系统终端于工程目录 |
| Quit | | ✅ | |

Workbench 嵌入模式（本仓库不做）会把 New/Open 换成 Refresh Input Data，Quit 换成 Close Icepak。

### 5.2 Edit(&E)　keyboard `e`

| 项 | 快捷键 | 状态 | 行为 |
|----|--------|------|------|
| Undo | Ctrl+Z | ◐ | 快照栈（cab 同款 50 层）；一期仅几何显隐 |
| Redo | Ctrl+R | ◐ | 注意：Icepak 是 **Ctrl+R** 不是 Ctrl+Y |
| — | | | |
| Find | Ctrl+F | ◐ | 树内查找（`tree_find_form`） |
| Show clipboard | | ⬜ | |
| Clear clipboard | | ⬜ | |
| — | | | |
| Snap to grid | | ⬜ | |
| Preferences | | ◐ | 单位/背景/鼠标；QSettings |
| Annotations | | ⬜ | |

另：对象级热键（全局）  
`Ctrl+E` Edit、`Delete` Delete、`Ctrl+A` Toggle active、`Ctrl+V` Toggle visible、`Ctrl+H` Toggle shading、`Ctrl+T` Open/close tree node、`Ctrl+M` Open/close model subtree、`Ctrl+X` Move、`Ctrl+C` Copy、`Ctrl+W` Toggle shading type。

### 5.3 View(&V)　keyboard `v`

| 项 | 状态 | 行为 |
|----|------|------|
| Summary (HTML) | ⬜ | |
| — | | |
| Location / Distance / Angle / Unit vector / Unit normal / Bounding box | ◐ | 一期 Bounding box + Location（拾取点坐标） |
| — | | |
| Traces ▶ Net info / Trace info | ⬜ | PCB 走线 |
| — | | |
| Markers ▶ Add / Clear | ⬜ | |
| Rubber bands ▶ Add / Clear | ⬜ | |
| — | | |
| Edit toolbars | ◐ | 显示/隐藏各组工具栏 |
| Default shading ▶ | ✅ | 见 §8.2 |
| Display ▶ | ✅ | 见下 |
| Visible ▶ | ✅ | 按对象类型 checkbox（`type_visible`） |
| — | | |
| Lights | ⬜ | `tdv_lights_edit` |

**Default shading**（`shading_type` 互斥）：

- Wireframe shading
- Solid shading
- Solid/Wire shading
- Hidden line shading
- — 
- Selected solid shading

默认建模模式 `wire`，查看器模式 `solid`（`autohex.tcl`）。本查看器打开工程后默认 **Solid/Wire**（更接近截图里有模型时的观感）；空场景无所谓。

**Display** 级联：

| 项 | 控件 | 默认 |
|----|------|------|
| Object names ▶ Current assembly / None / Selected | radio `type_visible(names)` 1/0/2 | None |
| Coord axes | check `tdv_axes` | ON（三联） |
| Visible grid | check | OFF |
| Origin marker | check | OFF |
| Display rulers | check | OFF |
| Display project title | check | OFF |
| Display ANSYS logo | check | ON |
| Display current date | check | OFF |
| Display construction lines / points | check | OFF |
| Display mesh | check `grid_display` | OFF |
| Mouse position | check | OFF（开则状态栏跟坐标） |
| Depthcue | check | OFF |
| Tcl console | check Win only | ⬜ 映射为 Python 控制台可选 |

### 5.4 Orient(&O)　keyboard `o`

| 项 | 快捷键 | 状态 |
|----|--------|------|
| Home position | `h` | ✅ |
| Isometric view | Shift+I | ✅ |
| Orient positive X | | ✅ 相机沿 +X |
| Orient negative X | Shift+X | ✅ |
| Orient positive Y | Shift+Y | ✅ |
| Orient negative Y | | ✅ |
| Orient positive Z | | ✅ |
| Orient negative Z | Shift+Z | ✅ |
| Zoom in | `z` | ✅ 框选放大 |
| Scale to fit | `s` | ✅ Fit all |
| Reverse orientation | Shift+R | ✅ |
| Nearest axis | | ✅ |
| Save / Clear / Write / Read user views | | ◐ QSettings 存相机 |

工具栏 Orient 组只放 **−X、+Y、−Z、Iso、Reverse**（`menus_icepak.tcl` 如此裁剪，不是菜单全集）。

### 5.5 Macros(&A)　keyboard `a`

菜单在 Tcl 里创建为空，运行时 `add_macro_commands` 从  
`%ICEPAK_ROOT%/icepak_lib/macros`（digest）按 `macro_subtype` / `macro_subsubtype` 两级 cascade 填入。

帮助锚点已出现的宏名（至少）：

- ATX / Micro-ATX chassis
- Angled Fin Heat Sink
- PCB
- Polygonal ducts
- Heat sink creation / Detailed heat sink creation
- Heat Pipe

规划：扫描 `icepak_lib/macros` + digest 字符串，生成只读菜单树；点击 → NYI。配置工具栏 **Macros Toolbar**（日文资源有 `Configure Macros Toolbar`）。

### 5.6 Model(&M)　keyboard `m`

| 项 | 状态 |
|----|------|
| Create object ▶ 18 类（见 §6.3） | ◐ 一期：在当前工程插入默认尺寸对象（写内存模型）；持久化二期 |
| — | |
| Radiation form factors | ⬜ |
| — | |
| Generate mesh | ⬜ |
| — | |
| Edit priorities | ⬜ |
| Edit cutouts | ⬜ |
| Create material library | ⬜ |
| Power and temperature limits | ⬜ |
| — | |
| Check model | ◐ 几何完整性：bbox、空 shape、未知类型（已有 parser 交叉验证） |
| Show objects by material / property / type | ◐ 按类型着色高亮 |
| Show metal fractions | ⬜ |

Create object 级联原文（顺序不可改）：

`blocks, blowers, enclosures, fans, heat exchangers, heat sinks, materials, networks, openings, packages, assemblies, printed circuit boards, periodic boundaries, plates, resistances, sources, grille, walls`

注意：菜单用复数短名；工具栏用 `object_type_title`（如 Blocks / Fans）。**domain/cabinet 不出现在 Create**（`type != domain`）。

### 5.7 Solve(&S)　keyboard `s`

| 项 | 状态 |
|----|------|
| Settings ▶ Basic / Advanced / Parallel | ⬜ 可只读展示 `problem` 解析结果 |
| Patch temperatures | ⬜（仅 transient） |
| — | |
| Run solution | ⬜ |
| Run optimization | ⬜ |
| Create Krylov ROM | ⬜ |
| — | |
| Solution monitor | ⬜ |
| — | |
| Define trials | ⬜ |
| Define report | ⬜ |
| — | |
| Diagnostics ▶ Edit .cas / .diag / .uns_out / optimization log | ◐ 用系统编辑器打开工程内对应文件（若存在） |

### 5.8 Post(&P)　keyboard `p`

| 项 | 状态 |
|----|------|
| Object face (node) / Object face (facet) | ⬜ |
| Plane cut / Isosurface / Point / Surface probe / Min/max locations | ⬜ |
| — | |
| Convergence / Variation / 3D Variation / History / Trials / Network temperature plot | ⬜ |
| — | |
| Transient settings / Load solution ID / Postprocessing units | ◐ 只读 |
| Load / Save post objects from/to file | ◐ 已有 `post_objects` 解析 |
| Rescale vectors | ⬜ |
| — | |
| Create zoom-in model | ⬜ |
| Power and temperature values | ⬜ |
| Workflow data ▶ CFD Post/Mechanical | ⬜ |
| Display powermap property | ⬜ |

### 5.9 Report(&R)　keyboard `r`

| 项 | 状态 |
|----|------|
| HTML report | ⬜ |
| Solution overview ▶ View / Create | ⬜ |
| Show optimization/param results | ⬜ |
| — | |
| Summary report / Point report / Full report | ⬜ |
| — | |
| Network block values / Fan operating points / EM heat losses / Solar loads | ⬜ |
| — | |
| Write Autotherm file | ⬜ |
| — | |
| Export ▶ Gradient Firebolt p2i / Cadence TPKG / SIwave temp / Sentinel TI HTC / RedHawk Back Annotation | ⬜ |

### 5.10 Windows(&W)　keyboard `w`

动态窗口列表（`set_path toplevel(windows_menu)`）。一期：Graphics / Message / 当前 Edit 对话框。可 checkable 切换可见。

### 5.11 Help(&H)　keyboard `h`

| 项 | 快捷键 | 状态 |
|----|--------|------|
| Help | F1 | ◐ 打开 `commonfiles/help/en-us/help/ice_ug`（若安装） |
| Icepak on the Web | | ✅ `https://www.ansys.com/Products/Electronics/ANSYS-Icepak` |
| Customer Portal | | ✅ `https://support.ansys.com/portal/site/AnsysCustomerPortal` |
| List shortcuts | Shift+? | ✅ 弹出热键表（`tdv_print_shortcuts`） |
| — | | |
| About Icepak | | ✅ 文案对齐 `show_about_icepak`：`ANSYS® Icepak® Version 2019 R3` + copyright |

---

## 6. 工具栏设计

风格：Icepak 为 **icon-only、分组、多行**。Qt 用 `QToolBar` + `addToolBarBreak()` 实现 2–3 行；`Qt.ToolButtonIconOnly`。  
`View → Edit toolbars` 控制各组 `setVisible`。

### 6.1 File commands　row 1

| 命令 | 图标 id（Tcl） |
|------|----------------|
| New project | `bw_newg` |
| Open project | `open_icon` |
| Save project | `save_icon` |
| Print screen | `print_icon` |
| Create image file | `icepak_paint` |

### 6.2 Edit commands　row 1

Undo (`bw_undo`) / Redo (`bw_redo`)

### 6.3 Viewing options　row 1

| 命令 | 图标 |
|------|------|
| Home position | `new_home_nuvo` |
| Zoom in | `zoom_nuvo` |
| Scale to fit | `scale_to_fit` |
| Rotate about screen normal | `view_rotate_normal` |
| One viewing window | `one_window_nuvo` |
| Four viewing windows | `four_windows_nuvo` |
| Display object names | `icepak_names_nuvo`（三态 cycle 0/1/2） |

### 6.4 Orientation commands　row 1

| 命令 | 图标 | 说明 |
|------|------|------|
| Orient negative X | `icepak_plus_x`（与 +X 共用） | 工具栏只有这一组轴，不是 ± 全套 |
| Orient positive Y | `icepak_plus_y` | |
| Orient negative Z | `icepak_minus_z` | |
| Isometric view | `icepak_iso` | |
| Reverse orientation | `icepak_reverse` | |

截图中可见 X/Y/Z 轴按钮即此组。

### 6.5 Model and solve　row 2

| 命令 | 图标 |
|------|------|
| Power and temperature limits | `power_setup` |
| Generate mesh | `icepak_mesh` |
| Radiation | `icepak_radiation` |
| Check model | `check_nuvo` |
| Run solution | `icepak_solve` |
| Run optimization | `icepak_optim` |

### 6.6 Postprocessing　row 2

| 命令 | 图标 |
|------|------|
| Object face | `icepak_object_face` |
| Plane cut | `icepak_plane_cut` |
| Isosurface | `icepak_iso_surface` |
| Point | `icepak_point_probe` |
| Surface probe | `icepak_post_probe` |
| Variation plot | `icepak_variation_plot` |
| History plot | `icepak_history_plot` |
| Trials plot | `icepak_trials_plot` |
| Transient settings | `icepak_transient` |
| Load solution ID | `icepak_solution_id` |
| Summary report | `icepak_summ_report` |
| Power and temperature values | `max_temperatures` |

### 6.7 Object creation　row 3（`object_tools`，插在最前 `at_end 0`）

由 `app_last_minute_extra_commands` 按 `object_type_list` 动态生成，图标 `icepak_$type`。  
**排除 domain**；material/profile 不可拖放创建。

建议固定顺序（与 Model→Create object 一致，domain 除外）：

| type | 工具栏短名 | PNG（guibase 已引用） |
|------|------------|----------------------|
| block | Blocks | `icepak_block.png` |
| blower | Blowers | |
| enclosure | Enclosures | |
| fan | Fans | `icepak_fan.png` |
| heat_exchanger | Heat exchangers | `icepak_heat_exchanger.png` |
| heatsink | Heat sinks | |
| material | Materials | |
| network | Networks | `icepak_network.png` |
| opening | Openings | `icepak_opening.png` |
| package | Packages | |
| assembly | Assemblies | |
| pcb | Printed circuit boards | |
| periodic | Periodic boundaries | `icepak_periodic.png` |
| plate | Plates | `icepak_plate.png` |
| resistance | Resistances | `icepak_resistance.png` |
| source | Sources | `icepak_source.png` |
| ventres | Grille | `icepak_ventres.png` |
| wall | Walls | `icepak_wall.png` |
| profile | （若在 type_list）Powermaps | |

图标文件：Tcl 从 `$icon_library` 加载 PNG；本机 `lib/icons` 目前以 XBM 为主，PNG 可能打进 digest。实现时：能从安装目录读则读，否则 `IceIcons` 按类型绘制（块=立方、风扇=圆环叶片、开孔=框、…）。

### 6.8 Object modification　row 3 `object_tools`

| 命令 | 图标 | 快捷键 |
|------|------|--------|
| Edit object | `icepak_edit_object` | Ctrl+E |
| Delete object | `icepak_delete_object` | Delete |
| Move object | `icepak_move_object` | Ctrl+X |
| Copy object | `icepak_copy_object` | Ctrl+C |

### 6.9 Alignment　row 3 `object_tools`

部分按钮是 **dual**（`command_make_toolbar` 的 `multiple`）：按住展开第二命令。

| 主 | 副（multiple） |
|----|----------------|
| Align and morph faces | Align faces - move only |
| Align and morph edges | Align edges - move only |
| Align and morph vertices | Align vertices - move only |
| Align object centers | |
| Align face centers | |
| Morph faces | |
| Morph edges | |

一期全部 NYI；按钮要在、要点得动（打日志）。

### 6.10 左竖条 TDV Strip（视口内侧）

截图：树与 3D 之间的窄图标列。对应 ICEM/TDV 交互条 + `lib/tdv/*.cur`。

自上而下（对标截图常见顺序，可按实机微调）：

| 按钮 | 光标资源 | 行为 |
|------|----------|------|
| Pick | `pick.cur` | 单击选对象（默认） |
| Box pick | `wb_boxzoom.cur` / `polypick.cur` | 矩形框选 |
| Circle pick | `circlepick.cur` | ⬜ |
| Rotate | `rot.cur` / `wb_rot.cur` | 拖转相机 |
| Pan | `trans.cur` / `wb_pan.cur` | 平移 |
| Zoom | `scale.cur` / `wb_zoom.cur` | 拖缩放 |
| Box zoom | `wb_boxzoom.cur` | 与 Zoom in 命令相同 |
| Show/Hide | | 切换选中对象 visible（Ctrl+V） |
| Blank / Unblank | `blank_png` / `unblank_png` | ⬜ |

互斥：Pick / Rotate / Pan / Zoom 为操作模式；默认 Pick。  
**三键鼠标**（Icepak 默认，见 Preferences → Mouse bindings）：左选、中转、右缩/菜单——与竖条模式叠加。

---

## 7. 导航面板（Project / Library）

### 7.1 标签

`init_icepak.tcl`：`tree_has_libraries 1`。

1. **Project**（默认）
2. **Library** — `icepak_lib` 材料/风扇/封装浏览器（`add_browser_commands` + `icepak_lib/browsers/*.tcl`）

### 7.2 Project 树固定节点（顺序锁定，对标截图 + 中文资源）

根节点 = 工程名（未打开时可用 `untitled` 或隐藏根、直接列节点）。

```
{project}
├─ Problem setup          问题定义
│    ├─ Basic parameters  基本参数
│    ├─ Title/notes       标题/备注
│    ├─ Parameters and trials  参数/试验
│    └─ Local coords      局部坐标
├─ Solution settings      求解设置
│    ├─ Basic settings
│    ├─ Advanced settings
│    └─ Parallel settings
├─ Groups                 组
├─ Post-processing        后处理
├─ Points                 点   （monitor / named points）
├─ Surfaces               面   （monitor surfaces）
├─ Trash                  垃圾箱
├─ Inactive               非活动对象
└─ Model                  模型
     ├─ Cabinet           （domain，始终存在）
     ├─ {Assemblies…}
     └─ {objects by type / flat / creation order}
```

树组织模式（右键或隐含命令，`commands_autohex.tcl`）：

- Sort：Alphabetical / Meshing priority / Creation order
- Organize：Flat / Types / Types+subtypes / Types+subtypes+shapes  
  默认 **Types**（`tree(detail)=1`），与多数截图一致。

### 7.3 Model 下对象

数据源：已有 `model_parser.ModelFile`。每节点：

- 图标：按 `kind` → `icepak_$kind`
- 勾选/眼睛：visible（`Ctrl+V` / `type_visible`）
- 激活态：active（`Ctrl+A`）；Inactive 节点收集 `active=0`
- 双击 / Ctrl+E：Edit 对话框
- 拖放：一期不做（Tk 支持拖到组）

**Visible 菜单** 与树类型文件夹联动：取消 `Blocks visible` = 隐藏所有 block actor。

### 7.4 右键菜单（对象）

| 菜单 | 状态 |
|------|------|
| Edit object | ✅ |
| Delete object | ◐ |
| Move / Copy | ⬜ |
| Toggle visible / active / shading | ✅ |
| Remove from group | ⬜ |
| Edit via spreadsheet | ⬜ |

组节点另有：Create / Rename / Delete / Activate all / Deactivate all / Delete all / Create assembly / Copy params / Save as project。

树本身：Find、Open/Close all、Open/Close model subtree。

### 7.5 Library 页

一期只读：列出 `icepak_lib` 下 materials / fans / packages / browsers。双击 → NYI「从库实例化」。  
`fan.tcl` / `package.tcl` 已在 `icepak_lib/browsers/`。

---

## 8. Graphics Window（3D）

### 8.1 视觉

- 背景：竖向渐变（`tdv_background_style=1` Top-Bottom Gradient，另有 Left-Right / Diagonal / Solid）
- 右上：ANSYS logo + `2019 R3`（`Display ANSYS logo`）
- 左下：方向三联（与世界轴一致；Icepak 电子冷却常用 Z 向上，相机平行投影 `ParallelProjectionOn` —— 当前代码已开，保留）
- 空场景：只有渐变 + 三联 + 水印 + Welcome
- 有模型：cabinet 线框绿 + 各类型实体色（沿用 `KIND_COLORS`，可再按 Icepak 默认调色板微调）

### 8.2 着色（`shading_type`）

| 模式 | VTK |
|------|-----|
| wire | 仅边 `SetRepresentationToWireframe` |
| solid | 表面着色，无边 |
| solid/wire | 表面 + 特征边（两 actor 或 `EdgeVisibilityOn`） |
| hidden line | 白/背景填 + 边 |
| selected_solid | 未选中线框，选中实体 |

当前 GUI 的 Line / Shading / Translucent 三档 **不够**；半透明改为对象级 `graph_transparency`（Icepak 每图类可调），不要用全局第三模式顶替 solid/wire。

### 8.3 交互

| 操作 | 3 键（默认） | 竖条模式 |
|------|--------------|----------|
| 选择 | 左键 | Pick |
| 旋转 | 中键拖 | Rotate |
| 平移 | Shift+中 或 中+右 | Pan |
| 缩放 | 右键拖 / 滚轮 | Zoom |
| 框缩放 | `z` 或 Zoom in | Box zoom |
| 适应 | `s` | |
| 主视角 | `h` | |

拾取：左键高亮 → 同步 Project 树选中。双击 → Edit。

### 8.4 分屏

`view_panes(mode)`：1 或 4（工具栏有 One / Four；Two 命令存在但未进默认工具栏）。  
一期：1 窗；4 窗用 `QGridLayout` 四个 VTK 或一个 renderer 四分（VTK `vtkRenderer` 多 viewport）。

### 8.5 视口右键（一期）

Edit / Hide / Display only / Scale to fit / 着色快捷 —— 其余 NYI。

---

## 9. Message Window

源：`guibase.tcl` `make_message_window`；截图底栏。

| 控件 | 行为 |
|------|------|
| 文本区 | 只读，`maximumBlockCount=5000`；启动时打印 64-bit 版本说明 + copyright（`init_icepak.tcl` 的 `$copyright`） |
| Verbose | checkbox：开则 DEBUG/网格细节；默认关 |
| Log | checkbox：是否把后续消息写入 `{project}/.ice_gui.log` |
| Save | 另存当前缓冲区为 `.txt` |

消息格式：可保持 cab 的 `[HH:MM:SS] LEVEL: msg`，颜色：普通黑、error 红（Tcl `mess "...\n" red`）。

启动样例（对齐安装版语气，不必逐字节）：

```
This is the 64-bit version
© 2026 ANSYS Inc. All rights reserved.
Unauthorized use, distribution or duplication is prohibited.
...
```

---

## 10. 图标与资源

### 10.1 安装目录可复用

- `lib/icepak/icepak-logo.ppm` / `*-bits.xbm` — About / 启动
- `lib/tdv/ANSYS_*.ppm` — 视口水印
- `lib/tdv/*.cur` — 竖条光标
- `lib/icons/*.xbm` — 部分 16×16 位图（`icepak_edit_object.xbm` 等）
- `guibase.tcl` 引用的 PNG 名列表（若 digest 可解则导出一份到仓库 `ice_assets/`）

**不要**把 ANSYS 商标 PNG 提交到 git（版权）。运行时从安装路径加载；缺失则矢量替代 + 文字水印 `ANSYS 2019 R3`。

### 10.2 `IceIcons` 必画清单

`new open save print undo redo home zoom fit rotate win1 win4`  
`axis_x axis_y axis_z iso reverse`  
`mesh radiation check solve optim`  
`block plate fan opening wall source grille heatsink pcb package enclosure assembly network blower periodic resistance material`  
`edit delete move copy`  
`face plane iso_surf point probe`  
`pick boxpick pan`  
`existing unpack quit`（Welcome）

缓存键 `(name, size)`，与 cab 相同。

---

## 11. 数据与命令流

```
Welcome / File
    ├─ Open dir  ─► icepak_parser.project.IcepakProject
    ├─ Unpack    ─► tzr.unpack ─► IcepakProject
    └─ New       ─► 空 ModelFile + 默认 domain

IcepakProject
    ├─ ProjectTree.populate()     problem / model / post / groups
    ├─ View3D.rebuild(scene)      shape_to_geometry（已有）
    └─ Message.log(load summary)

Tree/Draw 选中 ─► 高亮 actor
Edit     ─► Dialog(DetailsTable / 二期分页：Geometry / Properties / Info)
Save     ─► 二期：encoder 写回 model（decoder 已可逆）
Export   ─► export.py JSON/CSV
NYI 菜单 ─► Message WARN
```

脏标记：`self._dirty`；标题加 `*`；关闭前提示。

---

## 12. 技术路线（按 cabdecoding 落地）

1. **布局骨架先于功能**  
   与 `CAB_GUI_DESIGN.md` M1 相同：先让冷启动窗口和截图分区一致，再接线。
2. **Action 表驱动**  
   每个 Tcl `command_define` 第一参数（长名）作为 action id，菜单和工具栏只引用 id。NYI 统一 `_nyi(longname)`。
3. **解析库当后端**  
   不重新发明 model/problem；GUI 只消费 `icepak_parser`。
4. **VTK 只负责 Graphics**  
   几何构建已在 `ice_gui.py`（hexa/quad/cyl/polygon/circ/container）；迁到 `ice_view3d.py`，补 solid/wire、水印、Orient 相机。
5. **Headless 测试**  
   `enable_3d=False` 已有；扩展：断言 11 个菜单、Welcome 四按钮、树九个固定节点、工具栏组名、Message 三控件。
6. **不调用 icepak.exe 做 UI 自动化**  
   菜单以 Tcl 源为准；截图只校验分区与 Welcome。避免许可/交互依赖（cab 对 STpre 同样决策）。

---

## 13. 实现分期

### M1 — 骨架对齐（优先，对应「不再简陋」）

1. Welcome 模态四按钮  
2. 11 顶栏菜单全量（功能可 NYI）  
3. 工具栏分组 6.1–6.6 + 左竖条占位  
4. 左 Project/Library；Project 九个固定节点  
5. Graphics：渐变、三联、水印、空场景  
6. Message：Verbose/Log/Save  
7. 打开目录 / `.tzr` 仍走现有 parser，对象填入 **Model** 节点  
8. `tests/test_gui.py`：无 VTK 可构建

### M2 — 查看闭环

- Orient 全套 + Home/Fit/Zoom in  
- 五种着色  
- 类型 Visible 开关 + 树勾选  
- 拾取联动、双击 Edit 对话框  
- Object creation 工具栏可见（点击创建内存对象或 NYI）  
- Pack/Unpack、Export CSV/JSON  
- About / Shortcuts / 热键

### M3 — 编辑与后处理浅层

- Undo 快照、Move/Copy 对话框（数值平移）  
- Groups / Inactive / Trash 语义  
- post_objects 挂到 Post-processing 节点  
- Problem/Solution 节点只读展示 `problem_parser`  
- Library 只读浏览  
- 4 分屏

### 长期（保持 NYI）

网格器、求解器、辐射 FF、优化、宏执行、ECAD 导入、EM Mapping。

---

## 14. 测试计划

| 用例 | 断言 |
|------|------|
| `test_build_ui_headless` | 无 VTK 可构建；菜单 File…Help 共 11 个 |
| `test_welcome_buttons` | Existing/New/Unpack/Quit |
| `test_layout_panes` | Project/Library 页、Message 三控件、Graphics 标题或 widget |
| `test_project_tree_nodes` | 九个固定英文节点名 |
| `test_toolbar_groups` | File/Edit/Viewing/Orientation/Model and solve/Postprocessing |
| `test_open_tzr` | Model 下对象数 = parser；cabinet 存在 |
| `test_visibility` | 取消 Blocks visible → 无 block actor |
| `test_shading_cycle` | 五模式不抛错 |
| `test_nyi_logs` | 点 Run solution → Message 含 WARN |
| `test_orient_iso` | 相机变化（有 3D 时） |

---

## 15. 与 Tcl/手册追溯

| Icepak 源 | ice_gui 落点 |
|-----------|--------------|
| `menus_icepak.tcl` 工具栏/菜单 | §5 §6 |
| `commands_icepak.tcl` `command_define` | `ice_actions.py` |
| `commands_autohex.tcl` shading/tree/align | §5.3 §6.9 §7 |
| `commands_guibase.tcl` Orient/Display | §5.4 §8 |
| `autohex.tcl` Welcome / `shading_type` | §4 §8.2 |
| `init_icepak.tcl` tree flags / version_p | §3 §7 |
| `language_text_icepak_Chinese.tcl` 树标签 | §7.2（UI 默认英文，可切中文） |
| `language_text_icepak_English.tcl` help_define | Help 上下文 |
| `lib/tdv` | §6.10 §8 |
| User's Guide `ice_ug_sec_gui_main_window` | 主窗口分区验收 |

---

## 16. 验收标准

1. 冷启动窗口与用户截图分区一致：顶双行工具栏、左 Project 树九节点、中渐变视口 + Welcome 四按钮、底 Message 带 Verbose/Log/Save、视口左下三联、右上 ANSYS 2019 R3。  
2. 菜单 11 项名称与级联第一层与 `menus_icepak.tcl` 一致（独立模式）。  
3. 打开现有 `.tzr`（如 `avonics.tzr`）：Model 树对象可显隐，3D 有几何。  
4. NYI 项不崩溃，只打日志。  
5. `pytest` GUI headless 全绿。

---

## 17. 对象类型总表（创建 / 树 / 着色）

| kind | 树/菜单名 | 创建 | 几何 shape（parser） | 默认色（现 KIND_COLORS） |
|------|-----------|------|----------------------|--------------------------|
| domain | Cabinet | 否（工程自带） | hexa | 绿线框 |
| block | Blocks | 是 | hexa/cyl/… | 钢蓝 |
| plate | Plates | 是 | quad | 橙 |
| source | Sources | 是 | hexa/quad | 红 |
| fan | Fans | 是 | cyl | 青 |
| opening | Openings | 是 | quad | 黄 |
| wall | Walls | 是 | quad | 灰 |
| resistance | Resistances | 是 | hexa | 品红 |
| ventres | Grille | 是 | quad | 棕 |
| material | Materials | 是（无拖放） | none | — |
| part | Parts | CAD | container | 青灰 |
| package | Packages | 是 | hexa | 紫 |
| pcb | Printed circuit boards | 是 | hexa | 草绿 |
| heatsink | Heat sinks | 是 | hexa | 黄褐 |
| enclosure | Enclosures | 是 | hexa | 蓝灰 |
| assembly | Assemblies | 是 | container | 嵌套 |
| blower | Blowers | 是 | | |
| network | Networks | 是 | none/示意图 | |
| heat_exchanger | Heat exchangers | 是 | | |
| periodic | Periodic boundaries | 是 | | |
| profile | Powermaps | 是（无拖放） | | |

未知 kind：parser 已保证 26 工程 `unknown_object_types=[]`；GUI 用 DEFAULT_COLOR。
