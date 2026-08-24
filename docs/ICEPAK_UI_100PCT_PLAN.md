# ANSYS Icepak 19.5 (2019 R3) GUI 100% 对标设计规划

> 项目：D:/training/caedecoder/icedecoding（现有实现）
> 对标目标：C:/Program Files/ANSYS Inc/v195/Icepak/icepak19.5/bin.win64_amd/icepak.exe（ICE_GUI 100% parity）
> 参考路线：D:/training/cgns/cabdecoding（STpre 逆向项目，网格 / 宏 / ECAD 三线已验证）

---

## 0. 结论摘要（TL;DR）

1. **原版本质**：Icepak 19.5 的 GUI 是 **Tk 8.1（Wish，icepak.exe 原名 icepak81.exe，Scriptics 编译）+ ICEM 系 "guibase" Tcl/Tk 命令框架 + "tdv"（The Data Viewer，OpenGL 原生 Tcl 扩展）可视引擎 + BWidget 1.3.1 树控件 + Fluent 系 "form" 面板/notebook 编辑器**的组合。它不是 VB/MFC/Qt 程序——因此我们不需要仿"控件风格"，而是仿**命令/面板/树/视区行为契约**。
2. **逆向已拿到"权威级"素材**：菜单/工具栏/热键的**源码级定义**就放在 lib/icepak/menus_icepak.tcl（515 行，可直接逐行翻译成数据）；命令注册表（301 个命令 + 图标键）可从 commands_*.tcl 全量抽取；网格参数、编辑面板字段、树节点顺序、偏好项等都可在配套 Tcl/图标/语言文件中确认；GUI 书目（《ANSYS Icepak 电子散热基础教程》第 2 版第 3.4 节）给出了 9 大界面组件与全部右键菜单/交互流程的权威中文描述。
3. **现有实现是"同构骨架、只读查看器"**：PyQt5 + VTK；11 个顶级菜单、9 组工具栏、Project/Library 双树、VTK 7 形状/5 着色/Orient/拾取、Message 窗均已在，但与 100% 的差距集中在：**树/导航行为、3D 显示完整度、分类型对象编辑面板、网格面板与网格显示、求解/后处理/报告、宏动态注册、ECAD 全链路、写回编码器**。
4. **路线建议**：不重写骨架，做"**黄金规格（golden spec）驱动**"的补全：把逆向出的菜单/工具栏/热键/图标/树节点固化为机器可读规格（已生成 docs/icepak_gui_golden.json），运行时构建与规格一致；每条命令落地为 action（未实现显式 NYI 并写 Message）；网格/ECAD 采用 cabdecoding 已验证的 **probe -> model -> verify -> golden** 方法。
5. **合规红线**：不打包 ANSYS 的二进制/图标/翻译文本；图标矢量重绘（按图标键），界面名词按功能名许可使用；中文翻译自建。

---

## 1. 逆向结论：原版界面架构

### 1.1 技术栈（证据：bin.win64_amd / lib 目录 + PE 分析）

| 层 | 原版 | 证据 |
|---|---|---|
| 解释器 | Tk 8.1 for Windows（Wish Application） | icepak.exe VersionInfo：ProductName "Tk 8.1 for Windows"、OriginalFilename icepak81.exe、Company "Scriptics Corporation" |
| GUI 框架 | ICEM CFD 家族 "guibase"（Tcl 层 + 编译模块） | lib/guibase/guibase.tcl（菜单/工具栏/窗口入口）、commands.tcl（command_make_menu/toolbar/define）、settings.tcl |
| 3D 引擎 | tdv（The Data Viewer）：OpenGL 原生 Tcl 扩展，显示列表式场景图 | icepak.exe 内嵌 Tdv_Viewer、tdv_image(·)、tdv_geo(·)、tdv_axes、tdv_begin_op/tdv_end_op、tdv_pickable_tags；lib/tdv/*.cur 光标；bin.win64_amd/opengl/opengl32.dll |
| 树控件 | BWidget 1.3.1 ::Tree | package require -exact BWidget 1.3.1（guibase.tcl:318）；lib/bwidget/tree.tcl |
| 表格/网格编辑器 | Tktable（tkTable.tcl 封装） | lib/icepak/tkTable.tcl、bin 内 Tktable2.10.dll |
| 面板/表单 | Fluent 系 "form" 机制（form_init/form_frame/form_text/form_finish）+ notebook | object_edit_use_notebook 1、init_icepak.tcl 大量 form_* 用法 |
| 语言 | 英语/中文(EUC-CN)/日文(Shift-JIS) 三套 language_text_icepak_*.tcl | language_text_prefix=$app_dir/language_text_icepak_（init:331） |
| 偏好 | ~/.icepak_config、~/.icepak_defaults、~/.icepak_qnodes（可被 source 的 Tcl 变量脚本） | init_icepak.tcl:621-623；autohex.tcl:473-476,527-530 |
| 网格子应用 | AutoHex / "ICEM AutoModel"（Complete Hex Mesher） | lib/autohex/autohex.tcl（whoami=AutoHex）、params_auto.tcl（全量参数）、bin 内 mesher.exe/hdm.exe/tetra/.etc |
| ECAD | extension/iceecad.exe（Qt4，EDB/ANF/ODB++/IPC2581->ICB）、ecxml.exe（Electronics Cooling XML）、NETEX-G64（PCB 导入） | extension 目录 + strings 分析 |
| 求解队列 | IcBQS 批处理队列（lib/batch_queue/*.tcl，默认端口 6791） | icbqs_server.tcl:92、batch_queue.tcl |
| 编译模块 | 各目录 digest（Tcl 字节码缓存，EB C0 1C ... 加密头，无明文） | guibase/tdv/icepak/macros 的 digest 文件（本规划不依赖其内容） |

> 说明：主窗口装配（make_main_window/make_message_window/make_tool_windows）、BWidget 树的具体结点文本、对象面板字段布局等少量内容编译进了 digest，无法直接读取；本规划用**可读源码（菜单/命令/参数/语言文件）+ 出版教程 GUI 图文 + 运行时探针（若需要）**三方交叉还原，凡属推断处均已标注。

### 1.2 主窗口结构（9 大组件，权威描述：《电子散热基础教程》3.4.1 及图 3-31）

```
+-------------------------------------------------------------------------------+
| 项目名称（不允许中文字符）                                                       |
+-------------------------------------------------------------------------------+
| 主菜单栏：File Edit View Orient Macros Model Solve Post Report Windows Help     |
+-----------+-------------------------------------------------------------------+
| 快捷工具栏 | 行1: File commands | Edit commands | Viewing options | Orientation|
| （行1/行2/ | 行2: Model and solve | Postprocessing                            |
| 行3排布）  | 行3(object_tools): Object creation(18) | Object modification(4) |
|           |                        | Alignment(7)                             |
+-----------+----------------------------------+--------------------------------+
| 模型树     |    图形显示区域（3D 视区）        | 自建模模型工具栏行/对齐匹配命令栏|
| Project树 |    - 可拖左/下边界调整大小         | （同一排 or 竖直，靠原版布局）  |
| + Library |    - 所有对象/网格/后处理显示      |                               |
| 树         +----------------------------------+--------------------------------+
|           | Message 消息窗口（底部中央）        | 当前所选对象几何信息窗口（右下） |
+-----------+-----------------------------------+--------------------------------+
```

关键开关（init_icepak.tcl）：ICEPAK_USE_MENUBAR=1、ICEPAK_ONE_WINDOW=1（单窗口模式）、tree_on_left=1、tree_has_libraries=1、object_edit_use_notebook=1、allow_multiple_views=1、no_main_window_logo=1、mainwindow_menu_pad=0、default_side_family=WALL、selectbg_color=#99d9ea（树选中色）、job_home_direction=-z、job_listsort=creation_order（树排序默认值）、snap to grid 默认全域 100 份。

启动路径：guibase.tcl:749-756：top_setup -> make_main_window (viewer_win_orient=v) -> make_message_window -> make_tool_windows -> adjust_window_geometry；视口对象 tdv_default = .v.view；.v 的 Map/Unmap 与其它 toplevel 联动；关闭协议："Use the Done or Quit commands to dismiss the form or exit the program."（guibase.tcl:760-768）。

### 1.3 命令注册表（一切 UI 的"真气"）

原版机制：command_define {longname shortname icon cmd bubble helpurl whenactive ?dragoff_cmd?} 登记到全局 command 数组；command_set_text（本地化）、command_set_icon、command_set_tree_icon（树节点图标）、command_set_hotkeys。菜单=command_make_menu，工具栏=command_make_toolbar，两者都只登记 "command(all-menus/all-toolbars)"，最后 command_create_menus/create_toolbars 统一装配；对应"whenactive"决定何时可点（如 File 菜单在项目未打开时置灰）。

**我们的实现镜像**：新建 ice_actions.py 数据驱动的 CommandRegistry（YAML/JSON 规格见 docs/icepak_gui_golden.json，字段：longname/shortname/icon/bubble/hotkey/whenactive/url/dragoff），菜单/工具栏/热键/树图标全部由注册表生成；未完成的 action 统一 self.nyi(name) 写 Message（WARN），**保证菜单永远完整、点击永远走到真实执行路径**。### 1.4 菜单结构（100% 覆盖面，详见 docs/icepak_gui_golden.json）

| 顶级菜单 | 内容（一级条目 + 级联） |
|---|---|
| **File** | New project / Open project / Merge project / Reload main version / Save project / Save project as / Import!(CSV-Excel, IDF!(New board,Update board), IDX, Electronics Cooling XML, Powermaps!(Apache Sentinel TI, Cadence tab, Cadence Stacked Die tab, Gradient Firebolt i2p, RedHawk CTM), Networks, JEDEC PTD/JEP30) / Export!(ANSYS Electronics Desktop script, CSV-Excel, IDF, EC XML, Networks, JEDEC PTD/JEP30) / EM Mapping!(Volumetric, Surface heat losses) / Unpack project / Pack project / Cleanup / Print screen / Create image file / Command prompt / Quit。*Workbench 变体：无 New/Open/Save-as/Unpack/两个 JEDEC；首项 Refresh Input Data；Quit -> Close Icepak |
| **Edit** | Undo / Redo / Find / Show clipboard / Clear clipboard / Snap to grid / Preferences / Annotations |
| **View** | Summary (HTML) / Location / Distance / Angle / Unit vector / Unit normal / Bounding box / Traces!(Net info, Trace info) / Markers!(Add, Clear) / Rubber bands!(Add, Clear) / Edit toolbars / Default shading!(Wireframe, Solid, Solid/Wire, Hidden line, 分隔, Selected solid) / Display!(Object names!(Current assembly/No/Selected), Coord axes, Visible grid, Origin marker, Rulers, Project title, ANSYS logo, Current date, Construction lines, Construction points, Display mesh, Mouse position, Depthcue, Tcl console) / Visible!(每对象类型可见复选框) / Lights |
| **Orient** | Home position / Isometric view / ±X ±Y ±Z（6 向）/ Zoom in / Scale to fit / Reverse orientation / Nearest axis / Save user view / Clear user views / Write user views to file / Read user views from file（＋"User views"动态列表） |
| **Macros** | 运行时由 add_macro_commands() 从 icelib/macros/*.tcl（宏定义/宏子类/宏子子类三级）填充 —— 见 §1.13 |
| **Model** | Create object!(Blocks, Blowers, Enclosures, Fans, Heat exchangers, Heat sinks, Materials, Networks, Openings, Packages, Assemblies, Printed circuit boards, Periodic boundaries, Plates, Resistances, Sources, Grille, Walls) / Radiation form factors / Generate mesh / Edit priorities / Edit cutouts / Create material library / Power and temperature limits / Check model / Show objects by material / property / type / Show metal fractions |
| **Solve** | Settings!(Basic settings, Advanced settings, Parallel settings) / Patch temperatures / Run solution / Run optimization / Create Krylov ROM / Solution monitor / Define trials / Define report / Diagnostics!(Edit .cas, .diag, .uns_out, optimization log) |
| **Post** | Object face (node) / Object face (facet) / Plane cut / Isosurface / Point / Surface probe / Min/max locations / Convergence plot / Variation plot / 3D Variation plot / History plot / Trials plot / Network temperature plot / Transient settings / Load solution ID / Postprocessing units / Load post objects from file / Save post objects to file / Rescale vectors / Create zoom-in model / Power and temperature values / Workflow data!(CFD Post/Mechanical) / Display powermap property |
| **Report** | HTML report / Solution overview!(View, Create) / Show optimization/param results / Summary report / Point report / Full report / Network block values / Fan operating points / EM heat losses / Solar loads / Write Autotherm file / Export!(Gradient Firebolt p2i, Cadence TPKG, SIwave temp data, Sentinel TI HTC, RedHawk Back Annotation) |
| **Windows** | 运行时动态（toplevel 列表：Model 树、Message、各编辑器/绘图窗口...；含 checkable 显隐项） |
| **Help** | Help(F1) / Icepak on the Web / Customer Portal / List shortcuts / About Icepak |

### 1.5 工具栏（9 组，含命令到图标键；图标键原版在 lib/icons、BWidget images 与 icepak_lib/macros/toolbar_figs）

| 行 | 组 | 按钮（命令）到 图标键 |
|---|---|---|
| 主区行1 | File commands | New project->bw_newg，Open project->open_icon，Save project->save_icon，Print screen->print_icon，Create image file->icepak_paint（WB 变体：Save project, Refresh Input Data->refresh_icon, Print, Create image） |
| 主区行1 | Edit commands | Undo->bw_undo，Redo->bw_redo |
| 主区行1 | Viewing options | Home position->new_home_nuvo，Zoom in->zoom_nuvo，Scale to fit->scale_to_fit，Rotate about screen normal->view_rotate_normal，One viewing window->one_window_nuvo，Four viewing windows->four_windows_nuvo，Display object names->icepak_names_nuvo |
| 主区行1 | Orientation commands | Orient negative X->neg_X，Orient positive Y->pos_Y，Orient negative Z->neg_Z，Isometric view->iso，Reverse orientation->reverse |
| 主区行2 | Model and solve | Power and temperature limits->power_setup，Generate mesh->icepak_mesh，Radiation->icepak_radiation，Check model->check_nuvo，Run solution->icepak_solve，Run optimization->icepak_optim |
| 主区行2 | Postprocessing | Object face->icepak_object_face，Plane cut->icepak_plane_cut，Isosurface->icepak_iso_surface，Point->icepak_point_probe，Surface probe->icepak_post_probe，Variation plot->icepak_variation_plot，History plot->icepak_history_plot，Trials plot->icepak_trials_plot，Transient settings->icepak_transient，Load solution ID->icepak_solution_id，Summary report->icepak_summ_report，Power and temperature values->max_temperatures |
| object_tools 行3 | Object creation | 18 类：由 command_define "Create <type>" ... icepak_<type> 生成 -> 图标键 icepak_block/blower/enclosure/fan/heat_exchanger/heatsink/material/network/opening/package/assembly/pcb/periodic/plate/resistance/source/grille/wall（对应 lib/icons/*.png 系列） |
| object_tools 行3 | Object modification | Edit object->icepak_edit_object，Delete object->icepak_delete_object，Move object->icepak_move_object，Copy object->icepak_copy_object |
| object_tools 行3 | Alignment | Align and morph faces->auto_align_face（多态：Align faces - move only->auto_align_face_move），Align and morph edges->auto_align_edge（+move->auto_align_edge_move），Align and morph vertices->auto_align_vert（+move->auto_align_vert_move），Align object centers->auto_align_center，Align face centers->auto_align_centerface，Morph faces->auto_match_face，Morph edges->auto_match_edge |

> 语义要点（commands.tcl:118-218）：command_make_toolbar {longname rownum entries {at_end 1}}，rownum 1＝主工具区第 1 行；"1 object_tools"＝第 1 行的 object_tools 分区（Framework 把对象工具行单独成区，即"自建模模型工具栏+对齐匹配命令栏"）；at_end 0 前插（Object creation 前插）。支持 multiple（左/右键双命令，如 "Align and morph faces"/"Align faces - move only"——左键=拉伸对齐，右键=仅移动）与 cascade（工具栏内级联）。
> "Edit toolbars"（View 菜单）＝打开工具栏开关对话框，逐组显示/隐藏并记忆（command(all-toolbars) 序列）。

### 1.6 热键（79 条，menus_icepak.tcl:104-166 + 297-301）

应用级：F1 Help；Ctrl-F Find（Find in tree）；Ctrl-E Edit object；Delete Delete object；Ctrl-A Toggle object active；Ctrl-V Toggle object visible；Ctrl-H Toggle object shading；Ctrl-T Open/close tree node；Ctrl-M Open/close model subtree；Ctrl-S Save；Ctrl-P Print screen；Ctrl-Z Undo；Ctrl-R Redo；Ctrl-X Move object；Ctrl-C Copy object；Ctrl-N New project；Ctrl-O Open project；Ctrl-W Toggle shading type（wire/solid）；Ctrl-L Reload main version；Ctrl-D Refresh Input Data（仅 WB）。
视区级（tdv）：h Home；z Zoom in；s Scale to fit；Shift-X/Y/Z 负 X/正 Y/负 Z 定向；Shift-R Reverse；Shift-I Isometric；Shift-? List shortcuts；F5/F6/F7/F8 wireframe offset 设置/清零/增减；F9 toggle shift3 button；Control-E/A/T（视区内同样生效）。
编辑对齐交互：左键选择（先红后黄），中键接受，右键完成——见 §1.8。### 1.7 模型树（左侧，Project + Library 双树；tree_on_left / tree_has_libraries）

**Project 树**（图3-67；form_set_label_text 确认键名）：
```
<工程名>
+-- Problem setup            （物理问题、环境参数定义）
|   +-- Basic parameters      （瞬态/稳态、流体、湍流、重力/压力/温度、初始温度... -> problem 文件变量）
|   +-- Title/notes
|   +-- Parameters and trials （参数/试验变量）
|   +-- Local coords          （局部坐标系）
+-- Solution settings
|   +-- Basic settings
|   +-- Advanced settings
|   +-- Parallel settings
+-- Groups                    （分组管理）
+-- Post-processing           （后处理对象：Object face/Plane cut/Isosurface/Point/...全部挂此节点）
|   +-- Monitor points        （监控点 Points；可由树拖动对象创建）
|   +-- Monitor surfaces      （监控面 Surfaces）
+-- Trash                     （删除的对象进入垃圾箱）
+-- Inactive                  （拖入即抑制，从 Model 下消失）
+-- Model
    +-- Cabinet（计算域/系统）
    +-- 材料（Materials 节点：新建材料/库材料立即出现）
    +-- 类型分组（按对象类型分组的 "type (count)" 节点，每对象一个叶子）
    |   +-- 对象叶子：<name>  [active][visible][shading] 图标+文本
    +-- Assemblies / Networks ...（各自成组）
```
原版 BWidget 树行为：每节点可 bindText/bindImage；每"对象类型"在 View->Visible 下也有复选（type_visible）；树的显示层次可选（tree(detail) 0..3：flat / types / types+subtypes / types+subtypes+shapes），排序可选（job_listsort：creation_order / meshing priority / alphabetical，可在 Preferences/树右键切换）；Ctrl-T / Ctrl-M 开合单节点/整棵子树；Expand all / Collapse all。

- **Model 节点右键**（图3-70）：Create object / Find object / Load assembly / Object view（层次管理）/ Expand all / Collapse all（＋组节点：Create group / Rename group / Delete group / Activate all / Deactivate all / Delete all / Create assembly / Copy params / Save as project...）。
- **对象节点右键**（图3-71）：Edit（Ctrl-E/双击/右下角 Edit 也可打开）/ Add to clipboard / Summary report / Delete（入 Trash）/ Toggle active/visible/shading / Remove from group / Edit via spreadsheet（tkTable 批量编辑）/ Copy / Move（面板 dx/dy/dz）。
- **拖放**：对象 -> Inactive=抑制；对象 -> Trash=删除；对象 -> Monitor points=建监控点；材料/对象 -> 用户库=Paste from clipboard；Library 库项双击=实例化注入 Model 树。

**Library 树**（图3-69）：
```
Library（库）
+-- Main library（主库：icepak_lib 内 materials / object_library）
|   +-- Materials（材料库：fluids/solids/surfaces，80K 文本库，materials_from_libraries）
|   +-- Fans（轴流风机库）/ Blowers / Packages / Heatsinks / Filters / Components / TECs / ThermalInterfaceMaterials
|   +-- （library_info/library_name/library_read_only 标识）
+-- 用户库（Preferences->Libraries 新建，含 Materials 与 Model 库；位置/名字由 New library 面板设定）
```
右键：Paste from clipboard（从模型树剪贴板粘入材料/对象）/ New library / Rename / Delete / Browse 等。

### 1.8 3D 视区（tdv 功能全集 = 我们的 VTK 场景功能清单）

**视图/相机（View/Orient 菜单 + 热键）**：home（视角 = 默认，job_home_direction -z）、isometric、±X/±Y/±Z 定向、zoom in、scale to fit、reverse、nearest axis、rotate about screen normal（tdv_rotate_screen_y/z）、1/2/4 分屏（view_panes(mode)，可切换）、**user views 保存/清除/写文件/读文件（tdv_save_current_orientation 等）＋动态"User views"级联**、wireframe offset F5-F8、shift3 F9。

**显示对象（View->Display）**：Coord axes（坐标轴）、Visible grid（网格点阵，默认全域 100 份）、Origin marker、Rulers（标尺）、Project title、ANSYS logo、Current date、Construction lines/points（构造线/构造点）、**Display mesh（网格线显示）**、Mouse position（左下实时坐标）、Depthcue、Tcl console（Tcl 控制台开关）。后台：Lights 编辑（ambient/light1-4 颜色，problem 中 ambient_color/light1_color...）、背景样式（Solid/双色渐变，Background color1/color2；现实现已做 #9ec8e8->#f4f7fb 渐变）、Annotations（标题/日期/Logo 注记）、Set background、Track mouse。

**着色/命名**：Default shading（wireframe / solid / solid+wire / hidden line / selected solid）；Object names 三态（current assembly / none / selected，标签用 icepak_names 类图标+文本）；**每类型显示属性（Preferences->Object types）**：Color / Width(线宽) / Shading(允许实体) / Decoration(虚拟特征，如 Grille 百叶窗) / Font；每对象可覆盖（对象编辑器内 Solid/Shading/Texture 纹理）。对象透明度（graph_transparency）。

**对象/拾取/选择**：Pickable tag 集 obtype_all anno_pickable post_pickable；screen_select_all_types；**选面/边**：单击对象边->选中连接面之一，未中则重复单击循环（用于对齐/匹配）；框选（box pick，Shift=同类多选）、圈选（circle pick）、Blank/Unblank 选中对象；选择高亮 = 选中变红，二次选中变黄（对齐流程）。

**测量/标记**：Location / Distance / Angle / Unit vector / Unit normal / Bounding box（结果进 Message 窗 + 视区标注）；Markers（点标记）、Rubber bands（两点标记）、Traces（Net info/Trace info 粒子轨迹信息，trace 通道数据流）。

**交互/拖动（Preferences->Interaction）**：Motion allowed in direction X/Y/Z 勾选；Restrict movement to cabinet；Objects can't penetrate each other；Move object also moves group；Move object snaps to other objects；Snap attributes（cabinet 分辨率＝snap to grid 100 份）；New object size factor（默认 0.2＝新对象是 cabinet 各向尺寸的 20%）；Cabinet autoscale factor（≥1）；Move points with object。加 Mouse buttons 自定义（左/中/右功能映射）。

**对齐/匹配（Alignment 工具栏，红/黄交互）**：
- 面对齐 LMB：选中体->红面（中键接受）->被对齐体->黄面（中键接受）->右键完成＝**拉伸对齐**（左键命令）；RMB 命令＝**移动对齐**（不改尺寸）。
- 体中心对齐（仅左键）：小体->红->中键->大体->黄->中键->右键完成（小体移动）。
- 面中心对齐（仅左键）：红面/黄面中心重合。
- 面匹配 / 边匹配（仅左键）：红面/黄面形状位置一致（小体拉伸）。
- 支持选择延续（下次对齐自动提示上一结果）。

### 1.9 对象编辑器（Form + Notebook 机制，object_edit_use_notebook=1）

- 打开方式 4 种：选中后点"Edit"｜Ctrl-E｜树双击｜**右下角"当前所选对象几何信息窗口"的 Edit**（图3-75）。
- 面板结构（书 3.4.6 与图3-73/3-74/3-76/3-89）：notebook 标签约等于 **Info / Properties / Geometry**。
  - **Info**：名称、分组、创建顺序、优先级、active、类型/子类型、注释（图3-89）。
  - **Properties**：按类型全量字段（block：solid/fluid/不传热、材料、温度/热流量边界、CAD 类型 <- 由 model 文件 setval + object_edit_info($type) 字段定义驱动）。
  - **Geometry**：形状+参数（与右下角窗口完全一致：shape 下拉（hexa/quad/cyl/polygon/plate...）、尺寸、原点、坐标及 xS/yS/zS/xE/yE/zE 六个**橙色对齐按钮**（拉伸/起止点对齐）、Copy from（其他对象属性复制；Deactivate/Delete/Keep other object 单选项）、To location/Plane/Vector 等。
- **多体编辑**：Ctrl+单击逐一多选/Shift+单击首尾框选/Shift+框选同类；右键 Edit 或多体面板（同类合并编辑）；"Edit via spreadsheet"（tkTable 表格，行列=对象x属性，批量改值）。
- **spreadsheet/表格**：Tktable 封装（tkTable.tcl），我们以 QTableView + 代理模型实现（列头=属性，行=对象）。### 1.10 网格（AutoHex / Complete Hex Mesher）

- 入口：Model->Generate mesh（edit_grid_check_meshers -> edit_grid；生成前检测 mesher 可执行；生成中可 Cancel；大网格提醒 "Large mesh"）。
- 面板（六页签，参数全部来自 lib/autohex/params_auto.tcl，字段->默认值）：
  - **Basic**：grid_type、X/Y/Z size（或 max/min/ratio）与 grid_usesize_x/y/z/h、grid_max_elements=25000000、grid_gcount_i/j/k=10、grid_gtype=unif、grid_sep_x/y/z=0.001(m)、grid_gratio(i/j/k)（init/rat/dir）、grid_side_names（各类型侧边名）。
  - **Parameter**：三轴齿距控制（ratio 联动）、min/max 间距、grid_sep 等。
  - **Detail**：Mesher 预设（normal/coarse/null：min_elements_gap 3/2/1、min_elements_block 2/1/1、max_ratio 2/10/10000、conformal_tol 0.01、cyl_shrink_factor 0.99...）、Tetra（n_cells_in_gap、natural_size_refinement 32/8...）、**HDM/Mesher-HD**（mlm_auto_levels=2、icechip=1、feature_angle=40）、Smoother（limit_bad_angle=35、mth_local_sm=Optimize）、质量阈值（bad_face_align 0.05 等）、pipe（pipe_mesh_params on=0, ogrid_height 0.5）。
  - **Edit / Deletion / Others**：网格线增删（delete_grid_lines、protected 边界 B）、edge_eps/element_threshold/panel_block_face/check_scheme/part_mesh_option。
- 生成管线：参数写入 grid_params -> grid_generate + grid_compute_quality -> 输出 grid_input / grid_output(.cas 网格) / grid_errors / grid_mapping / mesh_timestamp；批处理作业同名文件 transient00.grid_params/model...。求解器一侧读网格出 .cas（Fluent 格式）+ uns_in/uns_out。
- **显示**：View->Display mesh（视区网格线，可抽稀/按单元显示）、模型树 Model 下可查网格统计；网格质量面板（Compute quality 结果）；"Large mesh" 警告。
- 关联编辑：Model->Edit priorities（对象网格优先级，mesh 顺序）、Edit cutouts（opening/fan/grille 挖空开关）、Radiation form factors（角系数）。

### 1.11 求解 / 后处理 / 报告

- **Solve 面板**：Basic（湍流模型、重力/高度、初始条件、时间步...=problem 变量）、Advanced（离散、欠松弛、SIMPLE...）、Parallel（进程/MPI）；Run solution->求解运行面板（迭代数、收敛判据、残差窗口=Solution monitor 选显示道）、Patch temperatures（瞬态初温设定）、Define trials（DOE 参数试验）、Define report（Summary 面板）、Create Krylov ROM、Run optimization、Diagnostics 四文本编辑器。队列化：批量 CLI（-batch_solve_id/-batch_report_file/-batch_just_check/-batch_just_report）+ IcBQS（-servers/-port(6791)/-mode/-use_ssl；submit -priority/-logfile/-server/-max_time；状态 RUNNING/QUEUED/TERMINATED/FINISHED/FAILURE/UNKNOWN）。
- **结果文件族**：transient00.resd(残差)、.mon_pt_N.out(监控点)、.fdat/.dat(场数据)、.cas、.uns_out/.uns_in、.overview/.pmon/.srp、solution id 概念（Load solution ID 切换不同 ID）。
- **后处理对象**（动态挂入树 Post-processing）：Object face(node/facet)——物体表面云图/矢量；Plane cut；Isosurface；Point；Surface probe；Min/max locations；Transient settings（时间步显示范围）；Postprocessing units；Rescale vectors；Create zoom-in model（局部细化模型）；Power and temperature values（与目标限值比较）；Display powermap property；Workflow data->CFD Post/Mechanical。
- **曲线**：convergence（残差）、variation（1D 沿直线）、3D variation、history（瞬态）、trials（试验）、network temperature。
- **报告**：HTML report、Solution overview（查看/创建）、Show optimization/param results、Summary（定量统计，templim_table 温度限值表）、Point、Full（定制）；Network block values（->Message 窗）、Fan operating points、EM heat losses、Solar loads、Autotherm 输出、五格式导出（Firebolt p2i / Cadence TPKG / SIwave temp / Sentinel TI HTC / RedHawk Back Annotation）。

### 1.12 ECAD（导入导出全链路）

- **管线**：iceecad.exe（EDB/ANF/ODB++/IPC2581 -> **ICB**（board_outline/layers/shapes/vias/nets）-> Icepak 对象（Show metal fractions 为铜箔）；NETEX-G64（PCB/ODB++/Gerber 导入，Qt5 前端）；ecxml.exe（**Electronics Cooling XML**：Component(Location/Size/Thermal(Rjc/Rjb/Power/Node)-JEDEC two-resistor/Delphi 家族——与 cabdecoding ecxml.py 完全同一格式族，可直接复用其 parse/export）。
- **菜单覆盖**：IDF(New board/Update board/Export)——由 lib/iges + IDEAS 等转换；IDX；ECXML I/O；Networks I/O；JEDEC PTD/JEP30 I/O；Powermaps（*Apache Sentinel TI profile* / *Cadence tab file* / *Cadence Stacked Die tab files* / *Gradient Firebolt i2p* / *RedHawk CTM*——均为文本/表格 profile，可逐格式解析）；EM Mapping（Volumetric/Surface heat losses，来自 HFSS/Maxwell/Q3D 的功率损耗映射）；ANSYS Electronics Desktop script（AEDT 脚本导出）；Autotherm；Firebolt p2i / Cadence TPKG / SIwave temp / Sentinel HTC / RedHawk 回标。
- **PCB 相关对象**：Create printed circuit boards（简单/详细 PCB，sandwich 等）；Show metal fractions；Show objects by material/property/type（按损耗/材料/类型高亮——ECAD 导入后常用）。
- **Workbench/AEDT**：icepakwb_server.tcl（服务器启动/端口/响应键）、aedt_extension/IcepakGridcutGL.exe（AEDT 内 gridcut 显示）、IcePakServer 协议。

### 1.13 宏（Macros）系统

- 菜单运行时构建：扫描 icepak_lib/macros/*.tcl（+用户 ~/icepak_lib/macros、工程目录 xxx_ib/macros）-> 每个宏声明 macro_definition(NAME)=脚本路径、macro_subtype、macro_subsubtype -> 组织成 **类型/子类型/宏** 三级级联；do_macro 执行；single_level_macro_menu 平铺模式。
- 内置宏库（icepak_lib/macros 目录 + 图/文档确认）：**angled_fin**（斜齿散热器）、**arcfin**、**blower**（离心风机）、**calc_params**（参数计算）、**Cavity-Down-BGA**、**delphi**(BGA/FLIP/LCC/QFP 模型)、**dual**、**flip_chip**、**fpbga**、**genwire**（wire bond 生成）、**pbga**、**qfp**、**sd**（split die?）、**siwave_auto**(VBS 自动化)、**sot_plastic**(SOT223/23/89)、**tec**（热电制冷器）、**simplify_pcb**、**Rotate block and plate**（书上确认）、**Icepak wizard**（向导型宏）、**ATX/Micro-ATX 机箱**（部分版本）；宏支持 *_figs 图示目录（向导页插图、教程图）、libraries/*（BGA/Cavity-Down-BGA/FPBGA/QFP 对象库）。
- 宏引擎= Tcl 脚本（.tcl 装载；.scm 是导出/批处理脚本；gawk/awk 工具链：genwire/simplify_pcb/remove_vertex）；Configure Macros Toolbar（宏工具栏自定义）。

### 1.14 其它外围

- **Welcome 对话框**：Existing(Open project) / New(New project 面板：Project name 不能含中文/路径) / Unpack(tzr) / Quit；上次工程列表。
- **命令行**：icepak19.5win64.bat（设 ICEPAK_ROOT/PATH 后启动）；开关 -viewer/-gdi/-ogl/-nodb/-batch/-use <file>/-regression 等。
- **Command prompt**＝Tcl/shell 窗口（file_shell）；View->Display->Tcl console 是视口内 Tcl 控制台；Text Editor（编辑 case/diag/uns/log）。
- **Print screen / Create image file**：netpbm 管线（ppm2tiff/ppm2png/pnmtopng...）另存图像；图元打印。
- **消息窗**：mess text color? ... 命令（red 等颜色分级）；记录测量/网格/求解/加载结果/快捷键列表（List shortcuts）/Show clipboard/Network block values；启动横幅（whoami/version/copyright）；底部状态行（topform_geo/botform_geo）。
- **Windows 菜单**：动态 toplevel 列表（Message、Model 树、编辑器、绘图窗等），checkable 显隐。

---

## 2. 现有实现 vs 100% 对标差距矩阵

> 依据子代理对 ice_gui.py / ice_panes.py / ice_icons.py / ice_create.py / icepak_parser / tests 的逐文件审计（详见 docs/current_implementation_inventory.md）。

| 子系统 | 现状（OK=已实现 / PM=部分 / NO=缺失） | 100% 对标缺口（按优先级） |
|---|---|---|
| 主窗口布局 | PM PyQt5 QMainWindow+QSplitter；标题 "ANSYS Icepak 2019 R3"；1600x900 | 缺"当前所选对象几何信息窗口"(右下)；缺项目名顶部条；缺欢迎窗后自动打开；缺 Windows 动态菜单；缺 bottom-right Edit 入口 |
| 菜单 | OK 11 个顶级菜单与黄金规格 1:1（含级联、热键文本） | 缺 Macros 动态注册；缺 Windows 动态列表；File WB 变体未区分 |
| 工具栏 | OK 9 组（图标 24px） | 图标为**自定义矢量风格**，未按图标键逐一还原；无 Edit toolbars 对话框；object_tools 区未单列；"multiple"双命令（左/右键）未做 |
| 热键 | OK 全部注册 | Control-A/V/H/E/T/M 部分未与选择联动；无视区 F5-F9/Shift 系列 |
| 模型树 | PM Project 9 节点+kind 分组；Library 只读 | NO 无树排序/组织切换（creation_order/priority/alphabetical；flat/types/...）；NO 无组节点右键全集；NO 无 Remove from group/spreadsheet；NO 无拖放（Inactive/Trash/Points/库粘贴）；NO Monitor points/surfaces 空；NO 无 Find（仅名匹配）、无 Find in tree 全文本；NO 树节点图标未按命令/类型图标键；PM 无 expand/collapse 全部/子树菜单 |
| 3D 视区 | PM 7 形状/5 着色/20 色/渐变背景/三联坐标/水印/KIND 拾取/1-4 分屏/名字三态 | NO 无网格显示 actor；NO Visible grid/Origin/Rulers/Title/Date/Construction/Depthcue/Mouse position 仅打勾无视觉；NO 无 2 窗；NO 无 box pick 多选/circle pick/Blank/Unblank；NO 无面/边选择（循环择面、红/黄高亮、中键接受）；NO 无对齐/匹配命令实现；NO 无 Lights；NO 无背景样式（solid/双色）切换与颜色设定；NO 无 per-type Color/Width/Shading/Decoration/Font；NO 无逐对象透明度；NO 无拖动移动对象（Interaction 规则）；NO 无 user views 保存/清除/文件；NO 无 markers/rubber bands/traces；NO 无测量工具（Location/Distance/Angle/...）；NO 无右/左下实时 Mouse position；NO 无 snap to grid；NO 无 Tcl console（相应提供 Python console） |
| 对象编辑器 | NO 仅只读 DetailsDialog | NO Form/Notebook 编辑器引擎；NO 18 类 x（Info/Properties/Geometry）逐类字段；NO 右下几何信息窗（橙色 xS/yS/zS/xE/yE/zE+拉伸对齐）；NO 多体编辑；NO spreadsheet（tkTable 等价）；NO Copy from；NO 材料选择/新建；NO CAD 类型 |
| 写回 | NO Save/Save as = NYI；无 _dirty | 编码器 encode_model（decoder 可逆，直接实现逆变换）；脏标记+关闭提示；Undo 全对象状态 |
| 网格 | NO Generate mesh=NYI；无面板 | NO AutoHex 六页签面板（参数表见 1.10）；NO mesher 调用管线/作业文件写出；NO 网格显示；NO 优先级/挖空面板；NO 质量统计 |
| 求解 | PM 仅只读展示 problem.setters | NO Basic/Advanced/Parallel 表单编辑；NO Run solution 面板+残差监控；NO Patch；NO trials/report；NO ROM/优化；NO 批队列 UI；NO solution ID |
| 后处理 | NO 全 NYI（仅有 post_objects 文本读写） | NO Form 后处理对象面板+视区云图/矢量/等值面/探针/极值；NO 6 种曲线；NO 瞬态设置；NO 单位；NO 缩放向量；NO zoom-in 模型；NO powermap |
| 报告 | NO 全 NYI | NO HTML/Summary/Point/Full/Overview；NO 网络块值/Fan 工作点/EM/Solar；NO Autotherm；NO 5 格式导出 |
| 宏 | PM 静态 7 条 | NO 动态三级注册扫描；NO 宏运行器（参数向导壳）；NO 内置宏库移植（参数化重建、图标）；NO Configure Macros Toolbar |
| ECAD | NO 全 NYI（仅 CSV/JSON 导出） | NO ECXML I/O（复用 cabdecoding ecxml.py）；NO IDF/IDX；NO Networks；NO Powermaps 五格式；NO JEDEC PTD/JEP30；NO EM Mapping；NO ICB/ODB++/ANF 管线（以 iceecad/netex 为 oracle）；NO Show metal fractions；NO AEdt/五格式导出 |
| 消息/状态 | PM MessageWindow（Verbose/Log/Save） | NO red 分级；NO 启动横幅；NO 测量/网格/求解进度消息规格化；NO 状态栏 4 段（坐标/模式/操作/目标/分组，参考 cabdecoding） |
| 偏好 | NO 无 | NO Preferences 7 页签（Display/Libraries/Object types/Interaction/Mouse buttons/Meshing/Units）；NO ~/.icepak_config 兼容（变量名级可导入导出）；NO Annotations |
| 语言 | NO 英文硬编码 | 增加 EN 完整表 + ZH 自译（参考原版键名 set* 语法做 tr("Problem setup") 字典）；i18n 模块 |
| 图标 | PM 矢量重绘（未按键对照） | 按 golden 图标键补齐 ~70 个（命名一致，风格对齐 16x16/24x24/32x32；BWidget 系 bw_* 与 icepak_* 说明） |
| 周边 | NO Command prompt/控制台/图像导出管线/打印 | Python console 等价 Tcl console；QImage 导出等价 netpbm；批部署 CLI 参数等价 |---

## 3. 总体技术路线（对齐 cabdecoding 已验证打法）

### 3.1 复用的三类工程范式（cabdecoding 已跑通）

1. **probe -> model -> verify -> golden**（网格/格式逆向）
   - *probe*：用"真身"作 oracle 探针（开发沙箱内运行 mesher.exe/hdm.exe/iceecad.exe/ecxml.exe 产出参考值），把输入-输出对应规则写成 JSON（等价 stpre_probe.py / probe_work/*.log）。
   - *model*：公式/结构体沉淀到实现（等价 stpre_rules.py -> cab_grid.py/cab_mesh.py）。
   - *verify*：与官方产物逐字节/逐行比对（等价 test_sxemt_export：structural==0、CXYZ atol=1e-15；我们的对象：model 文件往返、grid_params->grid_output、ECXML/IDF 对照）。
   - *golden*：把参考值钉进测试文件（等价 test_golden_reference.py：坐标/占用/hdr 常量）。
2. **GUI 同构 + headless**（cabdecoding CabViewer 模式）：主窗口/菜单/树/面板全部可在 enable_3d=False 下构建（我们已具备 HAS_GUI/headless 路径，保持）；面板与业务分离（ice_panes.py 模式继续），所有对话框经 QDialog+表单引擎。
3. **参数化部件宏 + 向导壳**（cab_parts.PRIMITIVE_KINDS + tess_for_spec + register_primitive；WizardBase._add_page + 导航树 + nav_status_icon）：Icepak 封装类宏（BGA/QFP/SOT/TEC/HS/FC...）全部做成"参数化部件+向导页"而非硬编码脚本；每一宏的 *_figs 只作为设计参考图，界面插图自绘。

### 3.2 工程结构（在现有 icedecoding 上渐进式扩展）

```
icedecoding/
+- ice_gui.py            # 主窗口装配（保留；增加右下几何窗/项目标题条/Welcome 流）
+- ice_actions.py        # 新：CommandRegistry（golden 驱动）+ 全部 action（含 NYI 通道）
+- ice_menus_toolbars.py # 新：由 registry 生成菜单/9 组工具栏/Edit toolbars/hotkeys
+- ice_tree.py           # 新：ProjectTree/LibraryTree（组织/排序/右键/拖放/图标/Find）
+- ice_view3d.py         # 新：VTK 场景（tdv 镜像 API：viewers/display/image 层/颜色表）
+- ice_forms.py          # 新：Form 引擎（form_init/frame/fields/notebook 标签，驱动编辑器与面板）
+- ice_editors.py        # 新：18 类对象编辑器（Info/Properties/Geometry）、多体、spreadsheet
+- ice_mesh.py           # 新：AutoHex 六页签、mesher 管线、网格显示、质量
+- ice_solve.py          # 新：求解设置/运行面板/监控/队列
+- ice_post.py           # 新：后处理对象/云图/曲线/瞬态；ice_report.py 报告
+- ice_macros.py         # 新：宏注册扫描/三级菜单/向导运行器/内置宏库
+- ice_ecad.py           # 新：ECXML/IDF/IDX/Networks/Powermaps/JEDEC/EM Mapping/ICB
+- ice_prefs.py          # 新：Preferences 7 页签 + .icepak_config 兼容读写
+- ice_i18n.py           # 新：en/zh 词典（键=原版 set*/form_set_label_text 键名）
+- ice_console.py        # 新：Python 控制台（Tcl console 等价）＋命令历史/回放
+- ice_log.py            # 新：mess(<text>, color) 消息总线（红色分级/横幅/日志）
+- icepak_parser/        # 现有：继续补编码器/ECXML/网格参数结构化/多边形顶点
+- tests/                # golden 外观测试 + 字节级往返测试 + headless 回归
```

### 3.3 分层策略

- **L1 数据层**（parsers + encoders）：icpak model/problem/grid_params/post_objects/tzr 已解码；继续：model **编码器**（decoder 逆）、grid_params 结构化、多 shape/polygon 顶点、problem 数组、ECXML、IDF/IDX、ICB、powermap 五文本、JEDEC、.cas/.fdat/.resd 读者（后处理用）。
- **L2 命令层**（ice_actions）：一条命令=一个对象（可测、可热键、可脚本回放）；未就绪->NYI。菜单/工具栏/热键从 registry 生成；"whenactive" 用谓词实现（无项目时 File 相关置灰...）。
- **L3 表现层**（ice_gui/ice_view3d/ice_tree/ice_forms）：VTK 场景维护对象 actor 组（名称/着色/透明度/选取标签）、视图命令集（home/iso/along/zoom/fit/reverse/nearest/user views/1-2-4 窗）、显示层（axes/grid/rulers/title/date/construction/mesh/names...）；树层维护语义。
- **L4 业务层**（mesh/solve/post/report/macros/ecad）：以 cabdecoding probe/golden 为标准验收。

### 3.4 关键算法/格式路线细目

| 主题 | 路线 | 交付/验收 |
|---|---|---|
| model 编码器 | 逆 v = c - KQ[i%7] - KC[i%16] - seed（decoder.encode_* 已备） | 往返 == 原文件（字节级，除我们新增对象外） |
| 网格显示 | VTK actor：结构化网格线（cell_division_lines 模式）、面网格、按类型半透明遮挡壳（参考 cab_vtk.mesh_block_display_actors） | 与 grid_output 单元数一致；Golden：网格线数与网格文件一致 |
| AutoHex 参数面板 | 直接按 params_auto.tcl 字段表造六页签；**ORACLE**：dev 沙箱运行 mesher.exe 对样例工程生成 grid_output 作参考 | 面板字段/默认值 100% 对表；生成结果与 oracle 网格拓扑一致（结构化 hexa 用公式化建轴：几何链 geometric_coords/calc_ratio 思想） |
| ECXML I/O | 复用 cabdecoding/ecxml.py（JEDEC two_resistor/Delphi，Location/Size/Thermal(Rjc/Rjb/Power/Node)），在 icpak 侧映射：ECXML Component->block/source/package 对象，导出同理 | 与 ecxml.exe 对同一样例互相读写（schema 级对等） |
| IDF/IDX | IDF 3.0 文本格式（官方公开 spec）：board outline + components + placement；DELEVICE 映射对象 | 与 Icepak 导入同一 IDF 的模型树/对象数一致（oracle 比对） |
| ODB++/ANF->ICB | 以 iceecad.exe 为 oracle：构造最小 EDB/ODB 样例->ICB 文本（board_outline/layers/shapes/vias/nets 结构已从 strings 取出），自实现 ICB 解析+几何还原 | 对象数/层数/铜箔信息与 iceecad 一致；Show metal fractions 数值一致 |
| Powermaps | 5 文本格式（tab/i2p/CTM/...)逐格式解析为 powermap 数据 | 与 ANSYS 导入同一文件的功率总量/分布一致 |
| 宏引擎 | 宏=参数向导（WizardBase 模式）+部件参数化（PRIMITIVE_KINDS 模式）；内置宏按 1.13 清单重建 | 每个宏：创建对象的参数/几何与官方宏产物模型文件 delta 为 0（oracle：官方宏跑出 .tzr 再 diff） |
| 求解 | 面板+运行编排（本工程若自研求解器：对接 transient00.uns_out/... 接口；或外部求解适配层） | UI 优先：面板/残差/监控/报告与官方一致 |
| 批队列 | IcBQS 语义（端口 6791、状态机、任务属性） | 与 icbqs_client 交互协议文本一致（或自实现等价调度） |

---

## 4. 分阶段实施计划（8 阶段，每阶段有独立验收）

**P0 基础地基（1 周）**
- 固化 golden 规格：docs/icepak_gui_golden.json（含菜单/工具栏/热键/图标键）+ 生成器 tools/gen_golden_spec.py（可重跑）。
- ice_actions.CommandRegistry ＋ ice_menus_toolbars 由 golden 生成真实菜单（替换硬编码），未实现 action=NYI 红色消息。
- 测试：test_golden_ui.py（菜单树/工具栏/热键 == golden；headless 可跑）。
- 验收：100% 菜单/工具栏/热键由数据驱动；原实现行为不回归（现有 40+ 测试全绿）。

**P1 壳层补齐（1-2 周）**
- 右下"当前所选对象几何信息窗口"（Geometry 只读 + 6 个橙色对齐按钮骨架 + Edit 按钮）。
- 顶部项目名、Welcome 流（Existing/New/Unpack/Quit）、New Project 面板（无中文校验）。
- Windows 动态菜单（topplevel 注册表）、Message/Project checkable。
- Edit toolbars 对话框；工具栏行布局 3 行（含 object_tools 区）；多命令（LMB/RMB）按钮 UI。
- 验收：截图与教程图 3-31/3-62/3-65 布局对齐。

**P2 树与导航（2 周）**
- 树组织/排序（flat/types/types+subtypes/types+subtypes+shapes；creation_order/meshing priority/alphabetical）；每类型图标键；展开/折叠全/子树；Ctrl-T/Ctrl-M。
- 右键菜单全集（Model 节点/组节点/对象节点/库节点）；剪贴板 Add/Paste（含库粘贴）；拖放（Inactive/Trash/Points/库）；Find/Find in tree；对象可见/活动/着色三态联动视区。
- Spreadsheet（QTableView+代理）；多选（Ctrl/Shift/框选）->多体编辑入口。
- 验收：树行为清单 40 项通过；与书图 3-67/3-69/3-70/3-71 一致。

**P3 3D 视区完整化（3-4 周）**
- 显示层：coord axes/visible grid/origin/rulers/title/date/logo 开关+视觉；construction lines/points；**Display mesh**（结构化网格线+抽稀）；背景样式（Solid/双色+颜色选择器）；Lights；Depthcue；Mouse position 左下角；名字 3 态完善；per-type Color/Width/Shading/Decoration/Font、per-object 覆盖与透明度。
- 交互：面/边选择（循环择面、红/黄高亮）、中键接受/右键完成的**对齐匹配编排器**（Align face LMB/RMB、Align centers(body/face)、Match face/edge）、box pick 多选、circle pick、Blank/Unblank、snap to grid（100 份）、拖动对象（Interaction 规则：方向/限制/不穿透/组联动/吸附）。
- 视图：2 窗；user views 保存/清除/写读文件/动态菜单；测量（location/distance/angle/unit vector/normal/bbox -> 消息+标注）；markers/rubber bands/traces（Net/Trace info）。
- 验收：1.8 功能清单全绿；对齐流程与书图 3-79..3-84 红/黄/中键行为一致。

**P4 Form 引擎 + 对象编辑器（4-6 周）**
- ice_forms.py（form_init/frame/row/col/field 类型：文本/复选/下拉/选择框/表格/色钮/几何示意... + notebook 页）。
- 18 类对象编辑器字段规格（来源：object_edit_info($type) 线索 + model setval 全集 + 书 3.4.6）：Info/Properties/Geometry 三页；右下几何窗与编辑器 Geometry 双写；橙色按钮（拉伸/起止点对齐）；Copy from 面板；材料选择与*Create material*。
- 多体编辑；spreadsheet 写回；Save/Save as 编码器落地（_dirty、* 标题、关闭提示）。
- 验收：任意教程工程对象 100% 可读改并可转回 model（往返字节一致，除有意变更）。

**P5 网格（4-6 周）**
- AutoHex 六页签面板（字段/默认值按 params_auto.tcl 全表）；优先级/挖空面板；mesh 管线（写 grid_params-> 自有 mesher 结构化生成（公式化建轴+边界自适应）-> grid_output/.cas 读者）；显示网格 + 质量；Large mesh 提示；Cancel meshing。
- ORACLE 并行：dev 沙箱跑官方 mesher.exe 采集样例，golden 判定（参考 cabdecoding test_golden_reference）。
- 验收：样例工程网格与官方拓扑一致（结构化网格面/点逐位比对 atol 1e-12 量级，官方为参照）。

**P6 求解与后处理（6-8 周）**
- Solve 三设置表单（直接编辑 problem 变量）、Run solution 面板+残差监控（Solution monitor）、Patch、Define trials/report、诊断文本编辑器、批队列面板（IcBQS 语义）。
- 后处理对象（Object face node/facet、Plane cut、Isosurface、Point、Surface probe、Min/max、Transient、Units、Rescale、zoom-in、powermap property、Workflow data）；6 曲线窗；报告全套（HTML/Summary/Point/Full/Overview/网络块/Fan/EM/Solar/Autotherm/5 导出）。
- 验收：对样例 .resd/.fdat 的曲线/数值与后处理面板行为一致。

**P7 宏系统（3-5 周）**
- 宏注册扫描（工程/用户/系统三层目录；三级级联；single_level 平铺；Configure Macros Toolbar）；宏运行器=向导壳（WizardBase 模式）+ 参数页 + 图示意。
- 内置宏移植（参数化重建，含 *figs 自绘）：1.13 全清单；库（object_library）浏览/实例化。
- 验收：每个宏的模型产物与官方宏产物 **model 文件 delta=0**（容差：命名/序号）。

**P8 ECAD + 批部署（4-6 周）**
- ECXML I/O（复用 cabdecoding ecxml.py）；IDF/IDX；Networks I/O；Powermaps 5 格式；JEDEC PTD/JEP30；EM Mapping；Show metal fractions；ICB/ODB++/ANF（oracle 驱动）；PCB 创建（简单/详细/sandwich）；五导出 + AEDT 脚本 + Autotherm。
- CLI/批部署参数 +Command prompt（Python console）+ QImage 导出（netpmp 等价）+ Print screen；批量解算队列。
- 验收：ECXML 与 ecxml.exe 互读；IDF 样例模型等价；powermap 数值一致。

**P9 收尾（持续）**
- i18n 完善（EN 键表+ZH 自译；原版键名优先，含中文语言文件转写为自有词典，不复制原文）；偏好持久化（.icepak_config 变量名兼容，读写各自的 JSON 且可导入导出）；启动横幅；快捷键列表；About；回归套件 golden 化；文档（本规划 + REVERSE_STATUS 更新）。

---

## 5. 测试与验收体系

1. **Golden UI 测试**（外观=规格）：test_golden_ui.py —— 运行时遍历 QMenu/QToolBar/QAction，与 docs/icepak_gui_golden.json 逐项符合（名称/层级/热键/图标键/顺序）；headless 可跑。
2. **行为清单测试**：将 1.4-1.14 的功能清单转 test_*.py（每个行为至少 1 断言，NYI 例外，NYI 数计入完成度）。
3. **字节/结构保真测试**（cabdecoding 标准）：model 编解码往返 ==；tzr 往返 ==；ECXML/IDF/ICB/grid_params 与 oracle 产物结构级对等；CSV/JSON 导出稳定。
4. **截图回归**：QTest + QPixmap 截图 golden（布局/颜色/图标出现），仅在 CI 有显示环境跑；参考图（教程截图）只作人工对照。
5. **性能**：datacenter 级工程（259 对象）加载 < 3s、旋转/缩放 60fps（VTK+降级 LOD）。
6. **Headless**：enable_3d=False 全链路（现有已具备）。

---

## 6. 风险与合规

| 风险 | 对策 |
|---|---|
| digest 编译模块内容不可读（树标签、网格对话框页签的真实控件树） | 三源交叉（可读 tcl 参数表 + 官方教程图文 + 开发沙箱运行时探针）；如仍缺，按"字段默认值=params_auto.tcl、布局=六页签共识"配置化实现并以教程截图核对 |
| ANSYS 商标/版权（图标、语言文件、digest、exe） | 本工程**不嵌入**任何 ANSYS 资产；图标按图标键矢量重绘；界面名词为功能性术语；中文翻译自建；工具脚本仅在本仓库内使用且只做格式/行为分析 |
| Oracle 依赖（mesher/iceecad/ecxml 需要在开发机运行） | 仅在开发沙箱做 probe；CI 不依赖；golden 数值以探针记录入 repo（参考 cabdecoding data/stpre_probe_*.json） |
| 求解器自研范围 | 本规划聚焦 **UI 100% 对标**；求解器为独立线，UI 侧先做面板/编排/数据消费者（.resd/.fdat/.uns_out 读取），求解内核另立任务 |
| 范围爆炸 | 每阶段有独立验收 + NYI 白名单可见（完成度度量）；优先"看得见、点得动、写得出" |

---

## 7. 交付物清单（本规划已产出）

| 文件 | 内容 |
|---|---|
| docs/ICEPAK_UI_100PCT_PLAN.md | 本文档 |
| docs/icepak_gui_golden.json | 机器可读黄金规格（11 菜单全树、9 工具栏、79 热键、70 图标键、File 双变体） |
| docs/icepak_gui_golden_summary.txt | 黄金规格人类可读打印 |
| docs/ref_icepak_gui_book.txt | 《ANSYS Icepak 电子散热基础教程》第 3 章 GUI 章节全文（参考） |
| docs/ICEPAK_UI_SPEC_REVERSE.md | 逆向出的完整界面规格书（菜单/树/3D/编辑器/网格/求解/后处理/报告/宏/ECAD/偏好/队列/Workbench，含证据路径与行号） |
| docs/current_implementation_inventory.md | 现有实现审计清单（功能/差距矩阵） |
| docs/cabdecoding_routes.md | cabdecoding 网格/宏/ECAD 路线摘要（可复用点） |
| tools/pe_strings.py | PE 字符串/导入表提取器 |
| tools/parse_commands.py / icon_lookup.py / gen_golden_spec.py | 命令注册表、图标键、黄金规格生成器 |
| tools/commands_registry.json | 301 命令注册表（含短名/图标键） |
| Icepak19.5_GUI_reverse_engineering_report.md | 子代理逆向报告（init/language/autohex/batch 全字段） |

> 下一里程碑建议：启动 **P0+P1**（地基锁规格 + 壳层补齐），随后按 P2->P8 推进，每阶段以本规划 4 验收表为准。
