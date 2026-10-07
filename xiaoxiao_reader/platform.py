"""导入 Tk 前修复 Tcl/Tk 环境并启用 Windows DPI 感知。"""
import os
import sys
import glob

def _修复tcl环境():
    """修复被污染的 TCL_LIBRARY / TK_LIBRARY 环境变量，
    强制指向当前 Python 解释器自带的 tcl/tk 目录"""
    python目录 = sys.prefix  # 例如 C:\Users\Ran\AppData\Local\Programs\Python\Python38

    def 找目录(模式):
        候选 = sorted(glob.glob(os.path.join(python目录, "tcl", 模式)))
        return 候选[0] if 候选 else None

    tcl目录 = 找目录("tcl8.*")
    tk目录 = 找目录("tk8.*")

    if tcl目录 and os.path.isfile(os.path.join(tcl目录, "init.tcl")):
        os.environ["TCL_LIBRARY"] = tcl目录
    else:
        os.environ.pop("TCL_LIBRARY", None)

    if tk目录 and os.path.isfile(os.path.join(tk目录, "tk.tcl")):
        os.environ["TK_LIBRARY"] = tk目录
    else:
        os.environ.pop("TK_LIBRARY", None)


def 初始化平台():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    if sys.platform != "win32":
        raise SystemExit("晓晓朗读目前仅支持 Windows。")
    _修复tcl环境()
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
