# 第三方组件与许可证声明

本文件只覆盖本项目实际依赖及 v1.0.1 Windows x64 构建所包含的组件。项目自有 Python 源码采用
[MIT License](LICENSE)，并不改变任何第三方组件的许可证。

## 运行时与发布包

| 组件 | 审计版本 | 用途 | 许可证/声明 |
| --- | --- | --- | --- |
| PySide6 Essentials | 6.9.3 | Python Qt 绑定、GUI 模块 | LGPL-3.0-only 或 GPL/商业许可；本发行包按 LGPL-3.0 使用。 |
| Qt 6（随 PySide6 Essentials 的动态库） | 6.9.3 | GUI、Widgets、SVG、平台插件 | LGPL-3.0（适用模块）或其他 Qt 许可；本发行包按 LGPL-3.0 使用。 |
| Shiboken6 | 6.9.3 | PySide6 绑定运行时 | LGPL-3.0-only 或 GPL/商业许可；本发行包按 LGPL-3.0 使用。 |
| CPython | 3.12.10 | PyInstaller 打包的 Python 运行时 | Python Software Foundation License Version 2。 |

`assets/licenses/LGPL-3.0.txt` 是 GNU LGPL v3 的原文，`assets/licenses/Python-3.12-PSF.html` 是 Python 官方
许可证页面副本；正式 ZIP 会将它们复制至 `LICENSES/`。Qt/PySide6
以动态库形式随 one-folder 包分发；使用者可替换相应动态库。Qt for Python 的许可证说明和源代码入口见
<https://doc.qt.io/qtforpython-6/licenses.html> 与 <https://code.qt.io/cgit/pyside/pyside-setup.git/>；Qt 源码见
<https://code.qt.io/cgit/qt/qtbase.git/>。CPython 许可证和源码见 <https://docs.python.org/3/license.html> 与
<https://github.com/python/cpython>。

## 构建与开发工具

下列工具用于开发、测试或构建，不作为应用功能依赖；其中 PyInstaller 的引导程序及其许可由生成产物的
PyInstaller 流程处理。

| 组件 | 审计版本 | 用途 | 许可证 |
| --- | --- | --- | --- |
| PyInstaller | 6.22.2 | Windows one-folder 打包 | GPL-2.0-or-later，附允许构建和分发非自由程序的特别例外。 |
| pywin32-ctypes | 0.2.3 | PyInstaller 的 Windows 构建依赖 | BSD-3-Clause。 |
| pytest | 8.4.2 | 测试 | MIT。 |
| pytest-qt | 4.5.0 | Qt UI 测试 | MIT。 |
| pytest-cov | 6.3.0 | 覆盖率集成 | MIT。 |
| coverage.py | 7.16.0 | 覆盖率 | Apache-2.0。 |
| mypy | 1.20.2 | 类型检查 | MIT。 |
| Ruff | 0.16.7 | 格式与静态检查 | MIT。 |

PyInstaller 的许可证和特别例外见 <https://pyinstaller.org/en/stable/license.html>。以上版本来自本地 v1.0.1
构建环境的包元数据；依赖升级时必须重新审计本文件和发行包中所附许可证。应用没有直接使用 keyring 或
pywin32；`pywin32-ctypes` 仅作为 PyInstaller 的构建依赖。

本文件提供归属和许可证定位，不构成法律意见。计划以商业许可、静态链接、替换 Qt 模块或更改打包方式发布前，
应进行独立的许可证合规审查。
