"""Tk 浮窗和屏幕框选；通过回调提交截图，不依赖快捷键控制器。"""
import ctypes
import json
import queue
import tkinter as tk
from .cards import 创建翻译卡片
from .paths import 位置记录文件
from .runtime import OCR忙碌, OCR请求队列, 翻译队列

def 开始屏幕框选(root, 提交截图):
    win = None
    def 清理():
        if win is not None:
            try:
                win.grab_release()
                win.destroy()
            except tk.TclError:
                pass

    def 取消(event=None):
        清理()
        OCR忙碌.clear()
        print("已取消 OCR 框选")

    try:
        from PIL import ImageGrab, ImageTk
        import importlib.util
        if importlib.util.find_spec("rapidocr_onnxruntime") is None:
            raise ImportError("缺少 rapidocr-onnxruntime")
        # 先截图再显示遮罩，避免把框选边框识别为文字。
        截图 = ImageGrab.grab(all_screens=True)
        左 = ctypes.windll.user32.GetSystemMetrics(76)
        上 = ctypes.windll.user32.GetSystemMetrics(77)
        宽, 高 = 截图.size
        win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{宽}x{高}+0+0")
        canvas = tk.Canvas(win, width=宽, height=高, highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        背景 = ImageTk.PhotoImage(截图, master=win)
        canvas.create_image(0, 0, image=背景, anchor="nw")
        canvas.背景 = 背景
        canvas.create_text(20, 20, anchor="nw", fill="#ff3333", font=("微软雅黑", 16),
                           text="拖动鼠标左键框选文字；Esc / 右键取消")
        起点 = []
        框 = canvas.create_rectangle(0, 0, 0, 0, outline="#ff3333", width=2)

        def 坐标(event):
            return max(0, min(宽, event.x)), max(0, min(高, event.y))

        def 按下(event):
            起点[:] = 坐标(event)

        def 移动(event):
            if 起点:
                canvas.coords(框, *起点, *坐标(event))

        def 松开(event):
            if not 起点:
                return
            x, y = 坐标(event)
            x0, x1 = sorted((起点[0], x))
            y0, y1 = sorted((起点[1], y))
            if x1 - x0 < 3 or y1 - y0 < 3:
                取消()
                return
            区域 = 截图.crop((x0, y0, x1, y1))
            清理()
            提交截图(区域)

        canvas.bind("<ButtonPress-1>", 按下)
        canvas.bind("<B1-Motion>", 移动)
        canvas.bind("<ButtonRelease-1>", 松开)
        win.bind("<Escape>", 取消)
        win.bind("<Button-3>", 取消)
        win.protocol("WM_DELETE_WINDOW", 取消)
        win.deiconify()
        win.update_idletasks()
        # SetWindowPos 使用绝对坐标，兼容位于主屏左侧的负坐标副屏。
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 左, 上, 宽, 高, 0x0040)
        win.lift()
        win.focus_force()
        win.grab_set()
    except Exception as e:
        清理()
        OCR忙碌.clear()
        提示 = f"OCR 框选失败：{e}"
        if isinstance(e, ImportError):
            提示 += '\n请在运行本程序的 Python 环境执行：\npython -m pip install Pillow rapidocr-onnxruntime'
        print(提示)
        翻译队列.put(提示)


def 翻译窗口线程(提交截图):
    root = tk.Tk()
    root.withdraw()

    状态 = {"win": None, "timer": None}

    # 读取上次记住的窗口位置（如果文件不存在或损坏，就用 None，走默认居中逻辑）
    记住的位置 = None
    try:
        with open(位置记录文件, "r", encoding="utf-8") as f:
            数据 = json.load(f)
            记住的位置 = (数据["x"], 数据["y"])
    except Exception:
        记住的位置 = None

    def 保存位置(x, y):
        nonlocal 记住的位置
        记住的位置 = (x, y)
        try:
            with open(位置记录文件, "w", encoding="utf-8") as f:
                json.dump({"x": x, "y": y}, f)
        except Exception as e:
            print("保存窗口位置失败：", e)

    def 关闭窗口():
        if 状态["win"] is not None:
            try:
                状态["win"].destroy()
            except tk.TclError:
                pass
            状态["win"] = None

    def 显示译文(文本):
        关闭窗口()

        win = tk.Toplevel(root)
        win.overrideredirect(True)      # 无边框
        win.attributes("-topmost", True)
        win.configure(bg="#1e1e1e")

        创建翻译卡片(win, 文本)

        win.update_idletasks()

        if 记住的位置 is not None:
            x, y = 记住的位置
        else:
            屏幕宽 = win.winfo_screenwidth()
            屏幕高 = win.winfo_screenheight()
            窗口宽 = win.winfo_width()
            窗口高 = win.winfo_height()
            x = int(屏幕宽 * 0.65 - 窗口宽 / 2)
            y = int(屏幕高 / 2 - 窗口高 / 2)

        win.geometry(f"+{x}+{y}")

        # ------------------------------------------------------
        # 拖动逻辑
        # ------------------------------------------------------
        拖动状态 = {"x": 0, "y": 0}

        def 开始拖动(event):
            拖动状态["x"] = event.x_root - win.winfo_x()
            拖动状态["y"] = event.y_root - win.winfo_y()

            if 状态["timer"] is not None:
                root.after_cancel(状态["timer"])
                状态["timer"] = None

        def 拖动中(event):
            新x = event.x_root - 拖动状态["x"]
            新y = event.y_root - 拖动状态["y"]
            win.geometry(f"+{新x}+{新y}")

        def 结束拖动(event):
            保存位置(win.winfo_x(), win.winfo_y())
            状态["timer"] = root.after(99000, 关闭窗口)  # 延长为 99 秒

        def 双击关闭(event):
            # 双击时直接关闭窗口，不需要等定时器
            if 状态["timer"] is not None:
                root.after_cancel(状态["timer"])
                状态["timer"] = None
            关闭窗口()

        # 子控件事件会经 Tk bindtags 传到所属顶层窗口，统一绑定避免重复回调。
        for 控件 in (win,):
            控件.bind("<ButtonPress-1>", 开始拖动)
            控件.bind("<B1-Motion>", 拖动中)
            控件.bind("<ButtonRelease-1>", 结束拖动)
            控件.bind("<Double-Button-1>", 双击关闭)  # 双击关闭窗口

        状态["win"] = win
        if 状态["timer"] is not None:
            root.after_cancel(状态["timer"])
        状态["timer"] = root.after(99000, 关闭窗口)  # 延长为 99 秒

    def 轮询队列():
        try:
            OCR请求队列.get_nowait()
        except queue.Empty:
            pass
        else:
            开始屏幕框选(root, 提交截图)
        try:
            while True:
                文本 = 翻译队列.get_nowait()
                显示译文(文本)
        except queue.Empty:
            pass
        root.after(100, 轮询队列)

    root.after(100, 轮询队列)
    root.mainloop()
