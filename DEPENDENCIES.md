# 依赖及卸载

源码运行只使用 Python 标准库，包括 Tkinter。验证使用 Python 3.14.6（Windows x64），本机已安装，复用；安装体积随 Python 发行方式变化，不确定。本次没有下载或全局安装新依赖。

构建工具 PyInstaller 6.21.0 已安装、复用，约 4.9 MiB；使用本任务已有虚拟环境。构建附带依赖约为 altgraph 0.17.5（0.1 MiB）、packaging 26.2（0.8 MiB）、pefile 2024.8.26（0.7 MiB）、pyinstaller-hooks-contrib 2026.6（1.1 MiB）、pywin32-ctypes 0.2.3（0.2 MiB）、setuptools 83.0.0（7.1 MiB），均已安装、复用。本工具不使用 Pillow、NumPy、FFmpeg 或网络下载组件。

EXE 内含 Python 和 Tcl/Tk 运行时，无需另装 Python。准确 EXE 文件大小见 Releases。构建源码见 build.py，许可原文见 licenses/。第三方来源：[Python](https://www.python.org/)、[PyInstaller](https://github.com/pyinstaller/pyinstaller)。

卸载 EXE：删除下载的 EXE 和相关文件即可。工具不添加服务、启动项、注册表或系统 PATH。删除报告文件由用户自行决定。

卸载自己建立的源码虚拟环境：关闭该环境内的程序后，删除 `.venv` 目录即可，不影响全局 Python。本机共享构建环境继续用于持续发布任务，本次不删除它。
