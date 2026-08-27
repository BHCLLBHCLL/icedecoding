# -*- coding: utf-8 -*-
"""P9: i18n — tr(key, lang) with EN identity table + own ZH translations."""
import os

_LANG = os.environ.get("ICE_LANG", "en").lower()

# Own ZH translations for the UI labels used by menus / tree / panels.
# (interface-functional terms; written for this project, not copied.)
ZH = {
    "File": "文件", "Edit": "编辑", "View": "视图", "Orient": "方向",
    "Macros": "宏", "Model": "模型", "Solve": "求解", "Post": "后处理",
    "Report": "报告", "Windows": "窗口", "Help": "帮助",
    "New project": "新建项目", "Open project": "打开项目",
    "Save project": "保存项目", "Save project as": "项目另存为",
    "Merge project": "合并项目", "Reload main version": "重新载入主版本",
    "Unpack project": "解包项目", "Pack project": "打包项目",
    "Print screen": "打印屏幕", "Create image file": "创建图像文件",
    "Command prompt": "命令提示符", "Quit": "退出",
    "Undo": "撤销", "Redo": "重做", "Find": "查找",
    "Show clipboard": "显示剪贴板", "Clear clipboard": "清除剪贴板",
    "Snap to grid": "网格吸附", "Preferences": "首选项",
    "Annotations": "注释",
    "Import": "导入", "Export": "导出", "EM Mapping": "电磁映射",
    "Create object": "创建对象", "Generate mesh": "生成网格",
    "Radiation form factors": "辐射角系数", "Edit priorities": "编辑优先级",
    "Edit cutouts": "编辑挖空", "Check model": "检查模型",
    "Show objects by material": "按材料显示对象",
    "Show objects by property": "按属性显示对象",
    "Show objects by type": "按类型显示对象",
    "Show metal fractions": "显示金属占比",
    "Run solution": "运行求解", "Run optimization": "运行优化",
    "Solution monitor": "求解监视", "Patch temperatures": "温度修补",
    "Define trials": "定义试验", "Define report": "定义报告",
    "Basic settings": "基本设置", "Advanced settings": "高级设置",
    "Parallel settings": "并行设置",
    "Plane cut": "切面", "Isosurface": "等值面", "Point": "点",
    "Surface probe": "表面取值", "Min/max locations": "极值位置",
    "Convergence plot": "收敛图", "Variation plot": "变化图",
    "History plot": "历史图", "Trials plot": "试验图",
    "Summary report": "汇总报告", "HTML report": "HTML 报告",
    "Point report": "点报告", "Full report": "完整报告",
    "Problem setup": "问题设置", "Solution settings": "求解设置",
    "Basic parameters": "基本参数", "Title/notes": "标题/备注",
    "Parameters and trials": "参数/试验", "Local coords": "局部坐标",
    "Groups": "组", "Post-processing": "后处理", "Points": "监控点",
    "Surfaces": "监控面", "Trash": "垃圾箱", "Inactive": "非活动对象",
    "Cabinet": "计算域", "Main library": "主库", "Materials": "材料",
    "Blocks": "块", "Fans": "风扇", "Blowers": "鼓风机",
    "Openings": "开孔", "Walls": "墙", "Plates": "平板",
    "Sources": "热源", "Packages": "封装", "Heatsinks": "散热器",
    "Resistances": "热阻", "Networks": "网络", "Assemblies": "组合",
    "PCBs": "印刷电路板", "Grilles": "通风孔", "Enclosures": "盒体",
    "Periodic": "周期边界", "Materials": "材料",
    "Display": "显示", "Default shading": "默认着色",
    "Object names": "对象名称", "Visible grid": "可见网格",
    "Origin marker": "原点标记", "Display rulers": "显示标尺",
    "Display project title": "显示项目标题", "Display current date": "显示当前日期",
    "Display mesh": "显示网格", "Mouse position": "鼠标位置",
    "Depthcue": "景深", "Lights": "灯光", "Visible": "可见",
    "user views": "用户视图", "Edit toolbars": "编辑工具栏",
}


def ui_language():
    return _LANG


def set_language(lang):
    global _LANG
    _LANG = (lang or "en").lower()


def tr(key, lang=None):
    """Translate a UI label key (identity for English / unknown keys)."""
    lang = (lang or _LANG).lower()
    if lang == "zh":
        return ZH.get(key, key)
    return key
