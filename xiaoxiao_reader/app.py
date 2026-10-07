"""快捷键注册、剪贴板读取与异步任务调度。"""
import asyncio
import time
import threading
import keyboard
import mouse
import pyperclip
import pygame
from .runtime import 按键映射, OCR忙碌, OCR请求队列, 翻译队列
from .text import 替换下划线为空格, 含中文, 是否是代码
from .speech import 朗读文本
from .translation import 翻译并显示
from .ocr import 识别截图
from .ui import 翻译窗口线程

_拖选_按下中 = _选中_按下中 = _截图_按下中 = False
主事件循环 = None
当前处理任务 = None


def 获取选中文本():
    哨兵 = "__CLIPBOARD_WAITING__"

    pyperclip.copy(哨兵)
    keyboard.press_and_release("ctrl+c")

    截止时间 = time.time() + 0.3
    文本 = 哨兵

    while 文本 == 哨兵 and time.time() < 截止时间:
        time.sleep(0.01)
        文本 = pyperclip.paste()

    if 文本 == 哨兵:
        return ""

    文本 = 文本.strip()
    pyperclip.copy(文本)  # 保留选中文本到剪贴板
    return 文本


async def 处理OCR截图(截图):
    try:
        print("正在 OCR 识别……")
        文本 = await asyncio.get_running_loop().run_in_executor(None, 识别截图, 截图)
        if not 文本:
            翻译队列.put("未识别到文字，请重新框选清晰的文字区域。")
            return
        print("OCR 识别结果：", 文本)
        pyperclip.copy(文本)
        await 处理选中内容(文本)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print("OCR 识别失败：", e)
        翻译队列.put(f"OCR 识别失败：{e}")
    finally:
        OCR忙碌.clear()


def 截图按下(event):
    global _截图_按下中
    if _截图_按下中:
        return
    _截图_按下中 = True
    if OCR忙碌.is_set():
        return
    OCR忙碌.set()
    pygame.mixer.music.stop()
    OCR请求队列.put(True)


def 截图抬起(event):
    global _截图_按下中
    _截图_按下中 = False


async def 处理选中内容(文本=None):
    if 文本 is None:
        文本 = await asyncio.get_event_loop().run_in_executor(None, 获取选中文本)
    if not 文本:
        print("没有检测到选中的文字")
        return

    朗读用文本 = 替换下划线为空格(文本)
    任务列表 = [asyncio.create_task(朗读文本(朗读用文本))]

    # 不含中文 且 不是代码 → 额外执行翻译；含中文或疑似代码则跳过翻译
    if 含中文(文本):
        pass
    elif 是否是代码(文本):
        print("检测到选中内容疑似代码，跳过翻译")
    else:
        任务列表.append(asyncio.create_task(翻译并显示(文本)))

    await asyncio.gather(*任务列表, return_exceptions=True)


async def 重新触发处理(截图=None):
    """取消上一次尚未完成的朗读/翻译任务，并启动新的一次"""
    global 当前处理任务

    if 当前处理任务 is not None and not 当前处理任务.done():
        当前处理任务.cancel()
        try:
            await 当前处理任务
        except asyncio.CancelledError:
            pass

    if 截图 is None:
        当前处理任务 = asyncio.create_task(处理选中内容())
    else:
        当前处理任务 = asyncio.create_task(处理OCR截图(截图))


def 拖选按下(event):
    global _拖选_按下中

    if _拖选_按下中:
        return
    _拖选_按下中 = True

    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

    # 单击一次，然后立即再按下并保持（即“双击按下”）
    mouse.click(button="left")
    mouse.press(button="left")


def 拖选抬起(event):
    global _拖选_按下中

    if not _拖选_按下中:
        return
    _拖选_按下中 = False

    mouse.release(button="left")

    if 主事件循环 is not None:
        asyncio.run_coroutine_threadsafe(重新触发处理(), 主事件循环)


def 选中按下(event):
    global _选中_按下中

    if _选中_按下中:
        return
    _选中_按下中 = True

    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

    if 主事件循环 is not None:
        asyncio.run_coroutine_threadsafe(重新触发处理(), 主事件循环)


def 选中抬起(event):
    global _选中_按下中
    _选中_按下中 = False


async def 主程序():
    global 主事件循环
    主事件循环 = asyncio.get_running_loop()

    keyboard.on_press_key(按键映射["拖选朗读"], 拖选按下)
    keyboard.on_release_key(按键映射["拖选朗读"], 拖选抬起)

    keyboard.on_press_key(按键映射["选中朗读"], 选中按下)
    keyboard.on_release_key(按键映射["选中朗读"], 选中抬起)

    print("=" * 40)
    keyboard.on_press_key(按键映射["截图朗读"], 截图按下)
    keyboard.on_release_key(按键映射["截图朗读"], 截图抬起)

    print("晓晓朗读已启动")
    print()
    print(f"按住 {按键映射['拖选朗读'].upper()}：双击按下鼠标左键")
    print(f"松开 {按键映射['拖选朗读'].upper()}：抬起鼠标左键并朗读选中文字")
    print(f"按下 {按键映射['选中朗读'].upper()}：直接读取当前选中的文字并朗读/翻译（不模拟鼠标选中）")
    print("（选中内容不含中文且不是代码时，会额外弹窗显示翻译结果）")
    print()
    print(f"按下 {按键映射['截图朗读'].upper()}：框选屏幕区域，OCR 识别后朗读/翻译；Esc 或右键取消")
    print("Ctrl+C 退出")
    print("=" * 40)

    while True:
        await asyncio.sleep(3600)


def 提交截图(截图):
    if 主事件循环 is not None and 主事件循环.is_running():
        asyncio.run_coroutine_threadsafe(重新触发处理(截图=截图), 主事件循环)
    else:
        OCR忙碌.clear()


def 启动常驻模式():
    已用扫描码 = set()
    for 功能, 键名 in 按键映射.items():
        try:
            扫描码 = set(keyboard.key_to_scan_codes(键名))
        except (ValueError, KeyError):
            raise ValueError(f"config/配置.ini 中“{功能}”的按键无效：{键名}") from None
        if not 扫描码 or 已用扫描码.intersection(扫描码):
            raise ValueError("三个功能需要不同且有效的按键。")
        已用扫描码.update(扫描码)
    threading.Thread(target=翻译窗口线程, args=(提交截图,), daemon=True).start()
    try:
        asyncio.run(主程序())
    except KeyboardInterrupt:
        print("\n程序已退出")
    finally:
        keyboard.unhook_all()
        if _拖选_按下中:
            mouse.release(button="left")
        pygame.mixer.music.stop()
