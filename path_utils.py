"""
资源路径工具 - 兼容开发环境和 PyInstaller 打包环境。

打包后 PyInstaller 会把资源解压到临时目录 _MEIxxxx，
使用 sys._MEIPASS 可以获取这个目录。
"""
import os
import sys


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发和打包环境。

    打包后（--onedir 模式）：资源在 exe 同级目录
    开发环境：资源在项目目录
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：使用脚本所在目录
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base_path, relative_path)


def app_data_path(relative_path):
    """获取用户数据目录下的文件路径（用于保存配置、数据库等用户文件）。

    这些文件不会被打包进 exe，而是存在用户目录下，
    这样升级软件时不会丢失用户数据。

    Windows: C:\\Users\\xxx\\AppData\\Roaming\\建华卫生所中医处方\\
    """
    app_name = "建华卫生所中医处方"
    app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), app_name)
    os.makedirs(app_data_dir, exist_ok=True)
    return os.path.join(app_data_dir, relative_path)


def exe_dir_path(relative_path):
    """获取 exe 同级目录下的文件路径。

    onedir 模式下，exe 同级目录存放一些用户可见的资源，
    如 tutorial、backup 等目录。
    """
    if getattr(sys, 'frozen', False):
        # 打包后：exe 所在目录
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境：项目根目录
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base_path, relative_path)
