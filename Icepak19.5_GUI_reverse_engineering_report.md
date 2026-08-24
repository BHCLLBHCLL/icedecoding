# ANSYS Icepak 19.5 GUI（Tcl/Tk）逆向分析报告

> 目标：`C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\lib`
> 结论先行：**Icepak 的主窗口 / 模型树 / 属性面板等核心界面代码并不在随附的 ` .tcl ` 源码里**，而是被编译进了 guibase 与 icepak 目录下的 ` digest `（Tcl 字节码缓存，二进制，无法直接读取）。本报告基于随附源码（` init_icepak.tcl `、` commands_icepak.tcl `、` menus_icepak.tcl `、` language_text_icepak_English.tcl `、autohex 系列、batch_queue 系列）给出的**可验证**字符串与行号，并对编译进 digest 的部分明确注明“源码不可见”。

---

## 1. init_icepak.tcl：主窗口创建序列

**重要说明**：` init_icepak.tcl ` 本身**不创建主窗口**，它只做“通用初始化”：
- 设置环境变量/全局开关（决定主窗口形态）；
- 加载 BWidget/tclxml/tkTable 库；
- 通过 ` load_fileset $app_dir $icepak_files "" `（L335）加载 Icepak 文件集；
- 非批量模式下 source 命令文件与菜单文件（L675-685）。

真正调用 ` make_main_window ` / ` make_message_window ` 是在共享 guibase 里：
- guibase\guibase.tcl L748-757：` top_setup ` → ` make_main_window $viewer_win_orient `（默认 ` viewer_win_orient=v `，L737）→ ` make_message_window ` → ` make_tool_windows ` → ` adjust_window_geometry `。` viewer_win_orient ` 取 ` v `，因此 3D 视口路径为 ` .v `，默认 TDV 窗口为 ` tdv_default = .v.view `（guibase.tcl L93）。

### 1.1 窗口标题（全局命名/版本，init_icepak.tcl）
- L111 ` set whoami "ANSYS Icepak" `
- L112 ` set product_display_name "ANSYS\u00AE  Icepak\u00AE" `（显示为 “ANSYS® Icepak®”）
- L113 ` set tool_name "Icepak" `
- L120-124：` major_vers=19 `、` minor_vers=5 `、` release_vers="2" `、` version=19.5 `、` version_p="2019 R3" `
- L154-161：logo 文件 ` icepak-logo-bits.xbm `、` icepak-logo.ppm ` 等；` tool_logo_make_real_small 1 `
- 启动“关于”框标题（init_icepak.tcl L860-866）：` form_init .about_icepak "About ANSYS Icepak" `；版权消息 L114-118（` © %Y ANSYS Inc. All rights reserved. ... `）
- 启动 splash（autohex_start.tcl L71）：` wm title .startup "Starting Ansys Icepak..." `

### 1.2 影响主窗口/布局的关键全局开关（init_icepak.tcl）
- L11 ` set env(ICEPAK_USE_MENUBAR) 1 ` → 使用菜单栏（guibase.tcl L607-614 据此置 ` mainwindow_menubar=1 `）
- L12 ` set env(ICEPAK_ONE_WINDOW) 1 ` → 单窗口模式
- L14-16 ` use_lnx_scheduler `（ICEPAK_NEW_LAUNCHER）
- L22 ` set tree_on_left 1 ` → 树在左侧
- L23 ` set tree_has_libraries 1 ` → 树含“库（library）”子树（` tree_make_library_subtree `，L414）
- L24 ` set no_main_window_logo 1 `
- L25 ` set mainwindow_menu_pad 0 `
- L26 ` set allow_multiple_views 1 `
- L27 ` set no_menu_tearoff 1 `；L28 ` use_builtin_file_dialogs 1 `
- L195 ` object_edit_use_notebook 1 ` → 对象编辑窗体用“笔记本(notebook 标签)”式布局
- L196 ` dont_perform_gap_check 1 `；L193 ` default_side_family WALL `
- L604 ` default_fluid_family FLUID `；L606 ` cad_data_to_units 1 `
- L321 ` from_Workbench ` 分支（保存/刷新命令，L15-31）

### 1.3 面板（Panes）
源码可见（guibase.tcl）：
- 主窗 = ` . `；3D 视口容器 = ` . ` 下由 ` make_main_window v ` 建立的 ` .v `；默认 TDV 视图 = ` .v.view `（L93）。
- ` make_message_window `（L755）创建消息窗口；` make_tool_windows `（L756），autohex 的 ` make_tool_windows ` 调用 ` make_edit_window `（autohex.tcl L695-697）。autohex 还定义右侧“编辑窗口/工具”按钮位置 ` tool_extra(1..7) `（Undo/Redo/View/Visible/Print/Prompt）与大按钮列 ` extra_position `（autohex.tcl L701-717）。
- 状态行：由 guibase 的 ` topform_geo / botform_geo ` 定位（guibase.tcl L739, L779-786）。
- 描述框（工具选择）：autohex.tcl L570-578 的 ` ice_dialog .new_job "Welcome to Icepak" ... {Existing New Unpack Quit} `（新建/打开/解包 .tzr）。**注意：真正的主窗口控件树 / panedwindow / toolbar / 状态条布局在 guibase\digest 与 icepak\digest（编译，不可见）。**

### 1.4 3D 视口区域
- ` set tdv_default .v.view `（guibase.tcl L93）；TDV 库在 ` $tdv_library `（autohex_start.tcl L95-104，` lib/tdv `）。
- 配色/光照：params_auto.tcl L207 ` tdv_lights_settings `（complex/ambient/light1..4 等）；L209 ` tdv_material_settings `；L35 ` background_color #000000 `；L36 ` vwindow_fills_screen 1 `。
- 视口朝向按钮集（autohex.tcl L719-731）：Home/Zoom/Scale to fit/Positive-Negative X/Y/Z/Isometric/Reverse，均作用于 ` .v.view `。
- 多窗口：` command_define "One viewing window"/"Two viewing windows"/"Four viewing windows" `（commands_autohex.tcl L367-377，` view_panes(mode) ` 1/2/4）。

### 1.5 模型树节点标签（MODEL tree）
源码可验证的“按类型分组的对象”来自三处：

**(a) Model 菜单 “Create object” 级联顺序（menus_icepak.tcl L384-403，精确顺序）：**
` Create blocks `、` Create blowers `、` Create enclosures `、` Create fans `、` Create heat exchangers `、` Create heat sinks `、` Create materials `、` Create networks `、` Create openings `、` Create packages `、` Create assemblies `、` Create printed circuit boards `、` Create periodic boundaries `、` Create plates `、` Create resistances `、` Create sources `、` Create grille `、` Create walls `。

**(b) 对象类型标题表（Japanese 语言文件中注释的 ` object_type_title `，键为英文，顺序即树分组）：**
` domain `(Cabinet), ` block `(Blocks), ` ventres `(Grille), ` enclosure `(Enclosure), ` heatsink `(Heat sinks), ` network `(Network), ` heat_exchanger `(Heat exchangers), ` opening `(Opening), ` periodic `(Periodic), ` source `(Source), ` pcb `(PCB), ` plate `(Plates), ` wall `(Walls), ` fan `(Fans), ` resistance `(Resistance), ` package `(Package), ` material `(Material), ` blower `(Blower), ` pipe `(Pipe), ` Highlight `(Highlight), ` part `(Assembly), ` part_sep `。
另有 ` object_type_title_short `：block/“Grille”/PCBs/“Heat exch”。
（说明：该表在 Japanese 文件中以 ` # ` 注释保留，运行时的实际标题由 params_auto.tcl L808 ` set object_type_title($type) [string totitle $type] ` 动态生成。）

**(c) 对象类型图标（guibase.tcl L391-401）——也即树分组名：**
` blocks `、` fans `、` plates `、` walls `、` openings `、` sources `、` grille `(icepak_ventres)、` resistances `、` heatexch `(icepak_heat_exchanger)、` periodic `、` network `。

**树组织/排序（commands_autohex.tcl）：**
- L660-670 “Sort tree” 按 ` alpha `/meshing priority/creation order（` job_listsort `）。
- L672-686 “Organize tree” 层次：flat(0)/by types(1)/types+subtypes(2)/types+subtypes+shapes(3)，控制变量 ` tree(detail) `。
- L688-702 “Open/Close all tree nodes”/“Open/Close all model nodes”。
- 树“库”子树：` tree_make_library_subtree `（init_icepak.tcl L414，setup_library_path）。

### 1.6 VIEW 树 / 后处理查看对象
“View”/“Post” 类对象（即见之于视图树的查看对象）来自 Post 菜单与 View 菜单（menus_icepak.tcl）：
- Post 菜单（L446-475）：` Object face (node) `、` Object face (facet) `、` Plane cut `、` Isosurface `、` Point `、` Surface probe `、` Min/max locations `、` Convergence plot `、` Variation plot `、` 3D Variation plot `、` History plot `、` Trials plot `、` Network temperature plot `、` Transient settings `、` Load solution ID `、` Postprocessing units `、` Load/Save post objects `、` Rescale vectors `、` Create zoom-in model `、` Power and temperature values `、` Workflow data / CFD Post-Mechanical `、` Display powermap property `。
- 命令定义见 commands_icepak.tcl：` post_create objsurface|planecut|isosurface|point `（L195-217）、` post_plot convergence|variation|3dgraph|history|trials `（L227-245）、` post_probe `（L223）。
- 显示开关（commands_guibase.tcl / menus_icepak.tcl View 菜单 L336-356）：` Coord axes `、` Visible grid `、` Origin marker `、` Display rulers `、` Display project title `、` Display ANSYS logo `、` Display current date `、` Display construction lines/points `、` Display mesh `、` Mouse position `、` Depthcue `、` Tcl console `。
> 注意：后处理对象在视图树中的实际分组（如 Object faces / Plane cuts / Isosurfaces / Points 等）生成代码在 icepak\digest，源码不可见。

### 1.7 对象属性面板机制
- 每个对象类型的属性表单字段由全局数组 ` object_edit_info($type) ` 描述；init_icepak.tcl L698-708 演示其结构：` foreach info $object_edit_info($t) { ... [concat [lindex $info 2] [list {cad CAD}]] ... }`（为 block/plate 增加 CAD 类型），元素形如 ` {param label {类型 控件 ...}} `。
- 编辑窗体用“笔记本/标签”化：` object_edit_use_notebook 1 `（L195）。` edit_update_button_active 1 `（autohex.tcl L37）。
- 表单由 guibase “forms” 模块构建：` form_init `、` form_frame `、` form_colwidth `、` form_rowheight `、` form_text `、` form_button `、` form_finish `（见 init_icepak.tcl show_about_icepak L865-893）。
- 属性面板操作命令（commands_icepak.tcl L389-391＝工具栏“Edit object”）：` tree_edit_current_selection `。
- 对象可见/激活等 ` command_define ... checkbutton type_visible($type) "update_type_visible $type" `（commands_icepak.tcl L465-470）。
- 属性编辑还支持“电子表格”方式：` tree_spreadsheet `（commands_autohex.tcl L437-439）→ 使用 tkTable.tcl（Tk Table 2.7 控件，含复制/粘贴/编辑绑定，见 tkTable.tcl L1-112）。

### 1.8 菜单栏与工具栏（menus_icepak.tcl）
- 主菜单（顺序）：` File `(L282)、` Edit `(L284)、` View `(L303)、` Orient `(L362)、` Macros `(L381)、` Model `(L383)、` Solve `(L421)、` Post `(L446)、` Report `(L477)、` Windows `(L505)、` Help `(L507)。
- File 菜单内容（含 新建/打开/合并/重载/保存/另存为/导入/导出/EM Mapping/解包/打包/清理/打印屏/创建图像/命令提示符/退出，L213-279）。
- 工具栏定义：File commands、Edit commands、Viewing options、Orientation commands、Model and solve、Postprocessing（L13-75）；Object modification、Alignment（L79-94）。
- 全局热键（L127-166，含 ` Control-t ` 打开/关闭树节点、` Control-m ` 打开/关闭模型子树等；TDV 热键 h/z/s 等）。

---

## 2. language_text_icepak_English.tcl：UI 字符串键

**关键事实**：` language_text_icepak_English.tcl `（196 行）**只是一张“帮助主题映射表”（` help_define `），不是完整 UI 字符串表**。每一行格式：` help_define \t "标题" \t "" \t <帮助主题1> \t <帮助主题2> `。它给出的是各功能/窗口的英文名（同时是 UI 标签），以及对应 Icepak 帮助手册的主题名。它是**英文默认字符串的集合**；中文/日文才用完整翻译数组（Chinese 是 EUC-CN、Japanese 是 shift-JIS，read 工具因非 UTF-8 无法直接读取）。

**帮助映射中出现的全部英文 UI 字符串（即对话框/菜单/标签名）——逐行列举：**
Main, Print options, Add marker, Lighting options, Find in tree, ATX / Micro-ATX chassis, Angled Fin Heat Sink, Annotations, Print options, Merge project, Save project, Save image, Graphics file_options, Clean up project data, CAD data, CAD data operation options, Select family, Change family, Multiple regions, IDF import, Board properties, Component selection, Traces, Save object, New unit name, Postprocessing units, Title notes, Open project, Preferences, Library name and info, Basic parameters, Cabinet, Move all objects in model, Move object, Move group, Move assembly, Snap to grid, Objects outside, Local coord_systems, Local coords, Copy object, Copy group, Copy assembly, Object selection, Anisotropic tensor, Materials, Selection, Temperature or velocity dependen, Temperature dependent fluid volu / visc / spec / diff / cond, Temperature dependent solid spec, Temperature value curve, Assemblies, Assembly contents, Networks, Network editor, Node, Link, Heat exchangers, Wires, Openings, Grille, Resistance curve, Sources, Curve specification, Printed circuit boards, Enclosures, Plates, Low side surface properties, High side surface properties, Walls, Wall external thermal conditions, Flow dependent heat transfer, Periodic boundaries, Blocks, Individual side specification, Temperature dependent power, Joule heating_power, Block thermal conditions, Fans, Fan curve, Blower_curve, Curve specification, Search fan library, Blowers, Resistances, Heat sinks, Interface thermal resistance, Bonding thermal resistance, Packages, PBGA Dimensions, Cavity Down BGA Dimensions, FPBGA Dimensions, Flip-Chip Dimensions, QFP Dimensions, DUAL Dimensions, PBGA/Cavity Down BGA/FPBGA/Flip-Chip/QFP/DUAL Substrate, ...Solder, Top side surface properties, PBGA/Cavity Down BGA/FPBGA/Flip-Chip/QFP/DUAL Die, Delphi Extraction, Search package library, Transient parameters, Square Wave Time-Step Parameters, Transient temperature / power / fan strength / X velocity / Y velocity / Z velocity / pressure, Transients, Time value curve, Set range, Transient_animation, History plot, Named point, Radiation specification, Radiation object selection, Form factors, Modify form factors, Parameters and optimization, Param value, Active parameter, Option parameter, PCB, Polygonal ducts, Heat sink creation, Detailed heat sink creation, Heat Pipe, Power and temperature limit setup, Save table, Mesh control, Per-object mesh parameters, Object priority, Advanced solver setup, Basic settings, Solution monitor parameters, Solution monitor definition, Modify point, Solve, Remote execution parameters, Parallel settings, Monitor, Email Project, Object face, Plane cut, Isosurface, Point, Min max locations, Object face contours, Plane cut contours, Isosurface contours, Object face vectors, Plane cut vectors, Isosurface vectors, Point vectors, Object face particles, Plane cut particles, Isosurface particles, Point particles, Variation Plot, Variation plot, Trials Plot, Trials plot, Version selection, Zoom-in modeling, HTML report, Solution, Define summary report, Report summary data, Define point report, Report point data, Full report, Report, Heat tr. coeff parameters。

> 这一节与 commands 定义相互印证（例如 “Basic settings/Advanced settings/Parallel settings” 对应 Solve 菜单 “Settings” 级联；“Mesh control/Per-object mesh parameters/Object priority” 对应六面体网格设置）。由于源码即为英文默认值，本文件是逆向 UI 标签最有价值的单条来源。

---

## 3. AutoHex（Complete Hex Mesher）UI

**来源文件与定位**：autohex.tcl（应用引导）、commands_autohex.tcl（命令集）、params_auto.tcl（全部网格参数与默认值）、check_auto.tcl（模型检查）、autohex_start.tcl（启动驱动）。
**重要说明**：网格对话框（“Basic/Parameters/Detail” 等标签页、每个字段控件）的实际布局位于 autohex\digest（` grid_auto.tcl `、` mesher_auto.tcl `、` hexa_auto.tcl `、` grid_params_table.tcl ` 等均被编译，源码不可见）。**可验证**的是窗口标题、命令集、以及 params_auto.tcl 提供的全部网格参数名与默认值（这些正是对话框里的字段/默认值）。

### 3.1 窗口/标题与入口
- ` set whoami AutoHex `、` set tool_name "ICEM AutoModel" `、` set tool_id automodel `、` set app_is_autohex 1 `（autohex.tcl L16-34）。
- 3D 视口：` set tdv_default .v.bot.f1.frame.f.f0.frame.one `（autohex.tcl L46）。
- 网格入口命令：` command_define "Generate mesh" "Mesh" icepak_mesh "edit_grid_check_meshers" `（commands_autohex.tcl L209-213）。
- 网格按钮：autohex.tcl ` add_mesh_button `（L645-693）把 “Mesh” 按钮加入 ` tool_phase_info($where) `，动作 ` edit_grid $has_auto ... `（L691），按可用 mesher（mesher/auto_mesher/global/tetra/cutter/smooth/hexa/iceboard_meshing/hdm）逐项检测。
- 模型检查：` command_define "Check model" "Check model" check_nuvo "model_check" `（commands_autohex.tcl L187-189）；check_auto.tcl ` model_check `（L8）输出 “Checking objects...”、统计 “N problem(s) was/were found for M object(s)”。

### 3.2 网格对话框字段（来自 params_auto.tcl 的网格参数与默认值）
总体类型/形状：` type_list = { domain hexa cyl tri incline quad circle container } `、` grid_type_list = { domain hexa cyl tri incline quad circle } `（L652-657）；对象名称 ` object_type_title(part)="Parts" `、` (part_sep)="Meshed sep. parts" `、` (group)="Group" `（L675-682）。

**全局/基本设置（grid_params，L321-350 定义键，默认值 L352-417）：**
- ` grid_type `（convert_multi / perobject 等）
- ` grid_usesize_x/y/z/h `（0），` grid_size_x/y/z `（=1），` grid_size_h `（=0）
- ` grid_max_elements ` = 25000000
- ` grid_gcount_i/j/k ` = 10；` grid_gtype ` = unif；` grid_gmax_i/j/k ` = 0；` grid_gmin_i/j/k ` = 0；` grid_hgrid ` = 0
- ` grid_set_default_sizes ` = 0；` grid_minglobal ` = 0；` grid_global_maxrat ` = 0
- ` grid_settings_type ` = normal；` grid_tetra_settings_type ` = normal
- ` grid_mesh_parts_separate ` = 1；` grid_different_subgrid ` = 1
- ` grid_cutouts ` = 1；` grid_partial_cutouts ` = 0；` grid_include_all_gaps ` = 0
- 间隙：` grid_sep_x/y/z ` = 1e-3，单位 m（L402-405）
- 比例(ratio)：` grid_gratio `（i/j/k 的 init=0, rat=1, dir=0）（L407-417）
- ` grid_ratios ` = 0
- 显示：` grid_display `、` grid_solid `、` grid_qtype ` = object、` grid_qual ` = facealign、` grid_cut_on `、` grid_cut_pct ` = 0.5 等（L419-444）
- ` grid_run_mesher ` = 1；` grid_force_remesh ` = 0；` grid_run_smoother ` = 0

**Mesher 预设（normal/coarse/null，L527-584）字段（即“网格器参数”页）：**
` min_elements_gap `(3/2/1)、` min_elements_block `(2/1/1)、` max_ratio `(2/10/10000)、` height_max `、` max_ogrid `、` min_cylinder_face `=4、` min_triangle_face `=4、` plate_join_tolerance `、` ignore_globals `、` ignore_perobject `、` no_group_ogrids `、` no_ogrids `、` cartesian `=0、` conformal `=1、` conformal_tol `=0.01、` cyl_shrink_factor `=0.99。

**Tetra（四面体）默认（L586-606）：** ` n_cells_in_gap `(2/1)、` edge_criterion `0.05、` natural_size_factor `0.8、` natural_size_refinement `(32/8)、` tetra_size_on_curves/surfs `、` tetra_ratio `、` split_spanning `。

**HDM 相关（L376-399, L476-491）：** ` grid_hdm_uniform `、` grid_hdm_aniso_uniform `、` grid_hdm_ssm `、` grid_hdm_mlm `、` grid_hdm_mlm_auto `=auto、` grid_hdm_mlm_auto_levels `=2、` grid_hdm_mlm_auto_prox `=1、` grid_hdm_mlm_auto_curv `=1、` grid_hdm_mlm_buff `=0、` grid_hdm_mlm_cartd `=0、` grid_hdm_icechip `=1、` grid_hdm_mlm_2d `=0、` grid_hdm_mlm_2d_type `=2、` grid_hdm_feature_angle `=40、` grid_hdm_clip_by_hollow `=1、` grid_hdm_refine_features `=0、` grid_highlight_block_sides `=1。

**Tetra/smoother 其它：** ` grid_tetra_sm `=1、` grid_tetra_smqual `=0.4、` grid_tetra_smiters `=10、` grid_tetra_smcoarse `=1、` grid_tetra_smcasp `=0.1、` grid_tetra_smciters `=1、` grid_tetra_auto_inter `=1、` grid_tetra_prisms `=0、` grid_tetra_prism_num `=4、` grid_tetra_prism_ratio `=2.0、` grid_tetra_prism_height `=0、` grid_tetra_prism_yplus `=0.001、` grid_tetra_prism_sms `=6、` grid_run_tetssi `=1、` grid_triangulation_tolerance `=0.00005、` grid_cutter_tries `=20、` grid_allow_addfaces `=1、` grid_no_tetra `=0、` grid_no_cutter `=0、` grid_cutter_surface `=0、` grid_tetra_oldstyle `=1、` grid_concurrency `=1、` grid_prism_families(ORFN) `=0。

**Smoother 参数（L634-648）：** ` limit_bad_determ `0.0、` limit_bad_angle `35.0、` mth_node_oriented_sm `0、` mth_local_sm `Optimize、` no_iter_local_sm `3、` max_level_local_sm `3、` no_step `1、` wght_orthog `1.0、` sfit `1、` ign_ps_points `0、` fix_bo `0。

**网格质量阈值（L715-718）：** ` bad_face_align `0.05、` bad_det_aspect `0.05、` bad_volume `1e-12、` bad_skewness `0.01。

**O-grid 管道网格（` pipe_mesh_params `，L307-313）：** ` on `0、` ogrid_height `0.5、` max_length `0、` init_height `0、` height_ratio `1.1。
**每对象网格（` grid_perobject `，L353/438）：** 0/1；` grid_tetra_params ` 等。

**网格类型→侧边名（L663-669）：** domain={
 minx maxx miny maxy minz maxz}、hexa={
 inside minx maxx miny maxy minz maxz}、cyl={
 inside bot top sides}、tri={
 inside bot top sides}、incline={
 inside bot top sides ...}、quad={
 bot top}、circle={
 outer inner}。

### 3.3 命令集（commands_autohex.tcl，构成 AutoHex 的菜单/工具栏项）
- 文件/工程：New project(L12)、Open project(L17)、Reload main version(L22)、Quit/Close(L27-37)、Print screen(L39)、Create image file(L43)、Command prompt(L47)、Merge project(L54)、Unpack/Pack/Email project(L155-165)。
- 导入：IGES points+lines、DXF points+lines、IGES/Step surfaces+curves、Step、DWG、ACIS、Tetin surfaces+curves、Gradient Firebolt i2p、Cadence tab、Cadence Stacked Die tab、SIwave profile、RedHawk CTM profile、Apache Sentinel TI profile（L60-110）；导出 IGES/Step/Tetin（L113-123）。
- 编辑/通用：Preferences(L127)、Title(L131)、Configure(L135)、Annotations(L139)、Rubber bands(L143-149)、Local coords(L151)、Undo/Redo(L167-173)、Groups(L175)、Summary(L179)、Summary(HTML)(L183)、Check model(L187)、Show objects by material/property/type(L192-203)、Snap to grid(L205)、Generate mesh(L209)、Edit priorities(L215)、Edit cutouts(L219)、Edit params(L223)、Define trials(L227)、CAD data 系列(L231-317)。
- 背景/着色：Top-Bottom/Left-Right/Diagonal Gradient、Solid、Background Style/Color/Color2(L319-345)；shading 系列 wire/solid/solid-wire/hidden line/selected solid(L619-642)。
- 视图窗口：One/Two/Four viewing windows(L367-377)、Display mesh(L363)、Object names(L347-361)。
- 对象操作：Move object(L381)、Copy object(L386)、Edit object(L391)、Delete object(L396)、Activate object(L401)、Open/close tree node/model subtree(L405-413)、Toggle object active/visible/shading(L421-431)、Remove from group(L433)、Edit via spreadsheet(L437)、Create group(L441)、Add/Remove group(by screen select/region/name-pattern)(L445-467)、Rename/Delete/Copy/Move/Edit group(L469-492)、Activate/Deactivate/Delete all in group(L494-504)、Create assembly from group(L506)、Copy params to group(L510)、Save group as project(L514)、Modify/Reset parameters(L518-524)、Copy parameters from(L526)。
- 对齐/变形（L532-607）：Align and morph faces/edges/vertices、Align faces/edges/vertices - move only、Align object centers、Align face centers、Morph faces、Morph edges。
- 树操作：Find、Show/Clear clipboard、Find in tree、Sort tree（alpha/priority/creation order）、Organize tree（flat/types/types+subtypes/types+subtypes+shapes）、Open/Close all tree/model nodes（L646-702）。
- 导入/导出 CSV/Excel（L704-710）。

### 3.4 网格如何构建
流程（源码可见）：` Generate mesh ` → ` edit_grid_check_meshers `（命令）→ 检测可用 mesher（autohex.tcl L645-693）→ ` edit_grid `（真实构建入口，在 digest）→ 调用网格器可执行文件（` $bindir/mesher `、` tetra `、` global `、` hexa `、` hdm `、` iceboard_meshing `、` smooth `、` cutter `，autohex.tcl L108-136 定位 ` *_path `）。` do_batch_job `（init_icepak.tcl L769+）在批量求解前调用 ` grid_generate ` 与网格质量计算 ` grid_compute_quality det_aspect/volume `（L787-789）。参数默认值由 params_auto.tcl 提供，并通过 ` grid_set_defaults normal `/` grid_set_tetra_defaults normal `（L629-630）写入当前参数。

---

## 4. batch_queue（Batch Queue）UI

**定位**：` lib/batch_queue ` 是**命名空间式的批处理队列库**（batch_queue.tcl 主库 + icbqs_client.tcl 客户端 + icbqs_server.tcl 服务端）。源码中**没有真正的对话框表单（无 ` form_init `）**——队列配置面板（主机/端口/队列）位于 Icepak/autohex 的应用 digest 中（入口见 autohex.tcl L463-465 ` if {$queue_server} { do_batch_queue_server } `，该过程定义在 digest）。本报告列出库面向的“设置项/字段/参数”。

### 4.1 系统与连接设置（batch_queue.tcl）
- 支持系统：` init_queue system `，system ∈ **IcBQS / PBS / GridEngine / Ansys**（` _verify_system ` L863-876，大小写不敏感，返回小写）。
- ` init_queue ` 选项（L148）：**` -servers <host列表> `、` -port <端口> `、` -mode `、` -pfunc `、` -use_ssl <0|1> `**。
- 默认：` batch_queue(port) ` = ` batch_queue_icbqs_server_port_default `（L141）；默认端口来自 icbqs_server.tcl L92：**` proc batch_queue_icbqs_server_port_default {} { return "6791" } `**（ICEM 客户端 L32-33 示例端口 6790，实际默认 6791）。
- 默认服务器：注释里 ` "localhost" `（L43 被注释，实际 servers 默认 “”）。
- ` init_queue ` 返回队列句柄 ` bqid `（=v_queue_serial 递增）。

### 4.2 任务提交参数（batch_queue::submit_job，L194-246）
` -priority <int> `（1=最高，默认 1）、` -dispatch <bool> `（默认 1，立即执行）、` -logfile <full-path> `（默认 /tmp 或 __NONE__）、` -server <hostname> `（默认选最空闲）、` -max_time <int> sec `。提交字符串模板 L214-215：` COMMAND \"$command\" LOGFILE \"$logfile\" MODE [BATCH_QUEUE] SYSTEM $bqs QUEUE $bqid PRIORITY $priority MAX_TIME $max_time `。
- 其它 API：` exec_job `、` exec_queued_jobs `、` queue_summary `、` delete_job `、` delete_all `、` delete_queue `、` get_job_status `、` add_job_message `、` add/get_job_attribute `、` is/are_jobs_running `、` highest_priority_queued_job `、` move_job `、` hold_job `、` resub_job `、` query_job `、` alter_job `、` get_job_elapsed_time `。

### 4.3 状态常量（batch_queue.tcl L27-69）
` SUCCESS `、` FAILURE `、` RUNNING `、` QUEUED `、` TERMINATED `、` FINISHED `、` UNKNOWN `；模式常量 ` REMOTE `、` LOCAL `、` BATCH_QUEUE `（L73-75）。

### 4.4 任务属性字段（_job_properties_list，L889-892）
` LOGFILE `、` COMMAND `、` HOST `、` MODE `、` PID `、` STATUS `、` PRIORITY `、` QUEUE `、` SYSTEM `、` MAX_TIME `、` START_TIME `、` STOP_TIME `、` MESSAGES `（存于 ` batch_queue_jobman ` 哈希，样例见 L894-909）。

### 4.5 客户端/服务器（icbqs_client.tcl / icbqs_server.tcl）
- 客户端：` batch_queue_icbqs_client_setup client_id -server_port <port> -servers <list> `（L35-79）；维护 ` icbqs_client_available_servers `、` icbqs_client_servers_sockets `、` icbqs_client_port `。
- 主机探测：` batch_queue_icbqs_client_setup_server { remote_hosts } `（L193-202）通过 ` rsh -n $rh "nohup tclsh $ICEM_ACN/lib/batch_queue/lib/icbqs_server_setup.tcl ..." ` 拉起远端队列服务。
- 空闲主机选择：` batch_queue_icbqs_client_get_idle_server `（L270-288，向服务器发送 ` batch_queue_icbqs_server_how_busy_are_you `）；` batch_queue_icbqs_client_exec_job `（L297）`、` kill_remote_process `（L344）、` remote_process_exists `（L366）。
- 远程执行环境由 ` build_queue_server `(digest) 与 ` $env(ICEM_ACN)/lib/batch_queue ` 组织；超时杀掉任务（` _update_job_status ` L1074-1083：若 ` max_time ` 超过则 delete_job 并 add_job_message）。

---

## 5. init_icepak.tcl：Registry / 首选项读取 & object_tools 工具栏

### 5.1 “Registry / 首选项”的读写（init_icepak.tcl）
Icepak 不使用 Windows 注册表（guibase/icepak 源码均无 ` registry ` 包），而是用 **HOME 下的三个首选项/状态文件**（L611-623，` confdir ` = ` $HOME `，Windows 下为 ` $USERPROFILE `；路径中反斜杠被替换成 /，L619）：
- **` global_pref_file ` = ` $confdir/.icepak_config `**（L621）——主首选项（等同“Registry”偏好）
- **` global_def_file ` = ` $confdir/.icepak_defaults `**（L622）——保存的默认参数值
- **` global_qnode_file ` = ` $confdir/.icepak_qnodes `**（L623）——批处理队列节点信息

读取时机在 autohex.tcl 的 ` tool_setup `：
- L473-476：` if [file exists $global_pref_file] { regsub -all \\ ... ; source $global_pref_file } `
- L527-530：同样读取 ` global_def_file `。
（首选项“Preferences”命令 → ` options_edit_auto `（commands_autohex.tcl L127-129）；Configure → ` file_options ` L135-137；相关文件集项 ` configfile `、` options_auto ` 在 guibase/autohex file 列表中，gui 逻辑在 digest。）

**其它“索引/库”读取：**
- 语言文件：` language_text_prefix = $app_dir/language_text_icepak_ `（L331），按 ` LANG `/语言表选择 English/Chinese/Japanese（guibase.tcl L663-733，language_table 中 English 为默认 ` { C } `，编码 “”；Chinese=euc-cn；Japanese=shiftjis）。
- 宏库：` library_path `（L370-415）＝ ` $ICEPAK_ROOT/icepak_lib ` + ` ~/icepak_lib ` + ` $ICEPAK_LIB_PATH `；从 ` $lib/macros/*.tcl ` 加载宏（` add_macro_commands ` L417-512），从 ` $lib/digests/*.digest ` 加载（` add_digest_commands ` L514-523）；` add_browser_commands `（L530-556）从 ` $lib/browsers/*.tcl ` 加载浏览器。
- Tcl/Tk 扩展：` package require BWidget `（L628-633）、` tclxml-3.2 `（L635-639）、Windows 下加载 ` Tktable.dll `（L663-665）、` tkTable.tcl `（L691-693）。

### 5.2 object_tools（对象工具栏）开关
- 对象创建工具栏：commands_icepak.tcl ` app_last_minute_extra_commands ` L473-476：
  ` if {![info exists no_object_creation_toolbar] && !$viewer_mode} { command_make_toolbar "Object creation" "1 object_tools" $create_object_commands 0 } `。
  —— 即只有当 ` no_object_creation_toolbar ` 未设置且非 ` viewer_mode ` 时才创建；位置/组名参数为 ` "1 object_tools" `（“1”表示可见标志，“object_tools”为工具栏分组名）。
- 其它挂到该组 “object_tools” 的工具栏（menus_icepak.tcl）：
  - L79-84 ` command_make_toolbar "Object modification" "1 object_tools" { "Edit object" "Delete object" "Move object" "Copy object" } `
  - L86-94 ` command_make_toolbar "Alignment" "1 object_tools" { "Align and morph faces" ... } `
- 每个对象类型通过 ` command_define "Create $lname" ... ` 生成创建命令，并 ` lappend create_object_commands `（commands_icepak.tcl L449-462），其名称来自 ` object_type_title($type) `；可见性命令 ` "$name visible" ` 加入 ` visible_object_commands `（L465-470），供 View 菜单 “Visible” 级联使用（menus_icepak.tcl L357）。
- 工具栏编辑入口：` command_define "Edit toolbars" ... "toolbar_edit" `（commands_guibase.tcl L15-18）；View 菜单 “Edit toolbars” 项（menus_icepak.tcl L327）。

---

## 6. 附：可用于核对的其它信息
- tkTable.tcl：Tk “Table” 控件（tkTable 2.7）默认绑定，提供复制/剪切/粘贴、拖拽选格、键盘编辑（tk_tableCopy/Cut/Paste 等），用于对象属性的电子表格式编辑（commands_autohex.tcl ` tree_spreadsheet `）。
- 关键命令/选项（commands_icepak.tcl）：Save project、Save as、New board/Update board（IDF）、Import/Export ECO/IFC/IDX/EC XML/Networks/JEDEC、Radiation、Radiation form factors、Create material library、Optimization and trials、Run optimization、Run solution、Create Krylov ROM、Delphi extraction、Solution monitor、Basic/Advanced/Parallel settings、Patch temperatures、Set up solution、Define report、各 post 命令、Summary/Point/Full report、Power and temperature limits/values、Autotherm、SIwave、Sentinel TI HTC、RedHawk Back Annotation、ADPI report、Time average、Write RIF file、CFD Post/Mechanical、Comfort level(PMV/PPD)、EM heat losses、Solar loads 等。
- 对象编辑信息数组示例（init_icepak.tcl L698-708）：为 block/plate 追加 “cad CAD” 类型。

---

## 7. 结论与限制
1. 主窗口、模型树/视图树、属性表单的实际构建代码位于 **guibase\digest 与 icepak\digest**（Tcl 字节码 digest，二进制，不可直接读取），本报告给出的是可验证的源码字符串、命令定义、菜单结构与全部网格参数默认值。
2. 英文 UI 字符串的“完整表”实际分散在 menus_icepak.tcl（菜单/工具栏）、commands_icepak.tcl / commands_autohex.tcl（命令+标签）、及 language_text_icepak_English.tcl（help_define 帮助映射=英文标签集合）；language_text_icepak_English.tcl 本身只有 196 行 help_define，不是完整本地化数组（中文/日文才是，且为非 UTF-8 编码）。
3. AutoHex（Complete Hex Mesher）对话框的标签页/字段布局在 autohex\digest；此处列出的字段名/默认值全部来自 params_auto.tcl，可作为“页签字段＋默认值”的可靠清单。
4. batch_queue.tcl 是库而非表单；队列配置面板（主机/端口/队列）在应用 digest，此处给出其受控参数、默认端口(6791)、状态常量与字段模型。

（以上所有字符串均为逐行核对后的精确引用；标注“digest/不可见”处为编译缓存，需用其它手段（如运行时 Tcl 动态读取）才能还原。）
