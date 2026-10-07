"""从剪贴板批量预生成语音及翻译缓存。"""
import os
import re
import time
import asyncio
from datetime import datetime
import pyperclip
import edge_tts
from . import runtime
from .paths import 预渲染日志文件
from .text import 选择朗读语音, 含中文, 预处理翻译文本
from .storage import 语音缓存键, 语音缓存文件路径, _写入语音缓存, 缓存键, 翻译缓存, 保存翻译缓存
from .translation import 调用翻译接口

预渲染单项重试次数 = 99
预渲染首轮并发数 = 32
预渲染补跑并发数 = 8


def 提取预渲染文本(文本):
    """
    按优先级提取：
    1. 单个英语单词
    2. 中文之间连续英语词组（禁止跨行）
    3. 连续英语词组（禁止跨行）
    4. 每行句子（禁止跨行）
    5. 每行完整文本（排在最后，跳过空行）
    """
    结果 = []
    已加入 = set()

    def 添加(项目, 类型):
        项目 = 项目.strip()
        # edge-tts 对单独的括号、花括号等纯符号文本不会返回音频。
        # 至少包含一个 Unicode 字母或数字时才加入预渲染队列。
        if not 项目 or not any(字符.isalnum() for 字符 in 项目):
            return
        # 语音缓存键忽略大小写；按同一规则去重，避免多个任务同时写同一个 MP3。
        去重键 = 语音缓存键(项目)
        if 去重键 in 已加入:
            return
        已加入.add(去重键)
        结果.append((类型, 项目))

    行列表 = 文本.splitlines()

    # 1. 单个英语单词
    for 行 in 行列表:
        for 单词 in re.findall(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b", 行):
            添加(单词, "单词")

    # 2. 中文之间的连续英语词组（同一行）
    for 行 in 行列表:
        for 匹配 in re.findall(r"[\u4e00-\u9fff]\s*([A-Za-z][A-Za-z\s'-]*[A-Za-z])\s*[\u4e00-\u9fff]", 行):
            添加(匹配, "中文夹英文词组")

    # 3. 连续英语词组（禁止跨行）
    for 行 in 行列表:
        for 匹配 in re.findall(r"\b[A-Za-z]+(?:\s+[A-Za-z]+)+\b", 行):
            添加(匹配, "英文词组")

    # 4. 每行句子（禁止跨行）
    for 行 in 行列表:
        行 = 行.strip()
        if re.search(r"[A-Za-z]", 行) and len(行.split()) >= 2:
            添加(行, "句子")

    # 5. 每行完整文本：确保中文、数字、单个符号等未被上述规则提取的行也会预渲染。
    # 已经以完全相同内容加入的行继续去重，避免并发写入同一个缓存文件。
    for 行 in 行列表:
        添加(行, "整行文本")

    return 结果


async def 生成预渲染音频(文本, 最大尝试次数=预渲染单项重试次数):
    """合成音频；对限流、服务端错误和空音频执行指数退避重试。"""
    使用语音 = 选择朗读语音(文本)
    最后错误 = "未收到音频数据"
    for 尝试序号 in range(1, 最大尝试次数 + 1):
        try:
            音频字节 = bytearray()
            communicate = edge_tts.Communicate(text=文本, voice=使用语音)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    音频字节.extend(chunk["data"])
            if 音频字节:
                return bytes(音频字节), 尝试序号, None
            最后错误 = "No audio was received"
        except Exception as e:
            最后错误 = str(e)

        if 尝试序号 < 最大尝试次数:
            等待秒数 = min(2 ** (尝试序号 - 1), 8)
            print(f"TTS 暂时失败，第 {尝试序号} 次重试：{文本[:40]}；{等待秒数} 秒后重试")
            await asyncio.sleep(等待秒数)

    return None, 最大尝试次数, 最后错误


async def 预渲染单项(类型, 文本, 最大尝试次数=预渲染单项重试次数):
    try:
        成功 = True
        # 语音缓存
        使用语音 = 选择朗读语音(文本)
        键 = 语音缓存键(文本, 使用语音)
        缓存路径, 文件名 = 语音缓存文件路径(键)

        缓存有效 = os.path.isfile(缓存路径) and os.path.getsize(缓存路径) > 0
        if not 缓存有效:
            音频字节, 尝试次数, 错误 = await 生成预渲染音频(文本, 最大尝试次数)
            if 音频字节 is not None:
                _写入语音缓存(
                    键, 文件名, 缓存路径, 文本, 音频字节
                )
                if os.path.isfile(缓存路径) and os.path.getsize(缓存路径) > 0:
                    状态 = "生成语音缓存"
                    if 尝试次数 > 1:
                        状态 += f"（第 {尝试次数} 次成功）"
                else:
                    状态 = "语音缓存写入失败"
                    成功 = False
            else:
                状态 = f"语音失败（已尝试 {尝试次数} 次）：{错误}"
                成功 = False
        else:
            状态 = "已有语音缓存"

        # 翻译缓存（仅英语内容）
        if not 含中文(文本):
            翻译键 = 缓存键(预处理翻译文本(文本))
            if 翻译键 not in 翻译缓存 and runtime.KEY:
                try:
                    译文 = await asyncio.get_running_loop().run_in_executor(
                        None, 调用翻译接口, 预处理翻译文本(文本)
                    )
                    翻译缓存[翻译键] = 译文
                    保存翻译缓存()
                    状态 += " + 翻译缓存"
                except Exception as e:
                    状态 += f" + 翻译失败：{e}"
                    成功 = False

        输出 = f"[{类型}] {文本} -> {状态}"
        print(输出)
        return 成功, 输出

    except Exception as e:
        输出 = f"[{类型}] {文本} -> 失败：{e}"
        print(输出)
        return False, 输出


async def 批量执行预渲染(项目, 并发数=None, 单项重试次数=预渲染单项重试次数):
    """使用固定数量的 worker，避免一次建立过多网络连接。"""
    if not 项目:
        return []

    if 并发数 is None:
        并发数 = 预渲染首轮并发数

    队列 = asyncio.Queue()
    for 序号, 项 in enumerate(项目):
        队列.put_nowait((序号, 项))
    结果 = [None] * len(项目)

    async def worker():
        while True:
            try:
                序号, (类型, 内容) = 队列.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                结果[序号] = await 预渲染单项(类型, 内容, 单项重试次数)
            finally:
                队列.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(min(并发数, len(项目)))]
    await asyncio.gather(*workers)
    return 结果


async def 执行预渲染():
    try:
        文本 = pyperclip.paste().strip()
    except Exception as e:
        print("读取剪贴板失败：", e)
        文本 = ""

    if not 文本:
        print("剪贴板为空")
        return False

    项目 = 提取预渲染文本(文本)
    print(f"提取 {len(项目)} 个预渲染项目")
    if not 项目:
        print("没有可预渲染的英语内容")
        return False

    日志 = [
        "# 晓晓朗读预渲染日志",
        "",
        f"- 时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- 数量：{len(项目)}",
        ""
    ]

    # Windows SelectorEventLoop 最多只能处理约 512 个 socket。使用固定 worker 池，
    # 防止项目较多时全量并发触发 "too many file descriptors in select()"。
    单项结果 = await 批量执行预渲染(
        项目,
        并发数=预渲染首轮并发数,
        单项重试次数=1,
    )

    # 整轮结束后再补跑最终失败项；已成功写入的缓存不会重复请求。
    失败序号 = [序号 for 序号, (成功, _) in enumerate(单项结果) if not 成功]
    if 失败序号:
        print(f"首轮仍有 {len(失败序号)} 项失败，等待 5 秒后补跑……")
        await asyncio.sleep(5)
        失败项目 = [项目[序号] for 序号 in 失败序号]
        补跑结果 = await 批量执行预渲染(
            失败项目,
            并发数=预渲染补跑并发数,
            单项重试次数=预渲染单项重试次数,
        )
        for 原序号, 新结果 in zip(失败序号, 补跑结果):
            单项结果[原序号] = 新结果

    信号 = [输出 for _, 输出 in 单项结果]
    成功状态 = [成功 for 成功, _ in 单项结果]

    日志.append("```\n" + "\n".join(信号) + "\n```")

    try:
        os.makedirs(os.path.dirname(预渲染日志文件), exist_ok=True)
        with open(预渲染日志文件, "w", encoding="utf-8") as f:
            f.write("\n".join(日志))
        print("日志已保存：", 预渲染日志文件)
        日志成功 = True
    except Exception as e:
        print("日志保存失败：", e)
        日志成功 = False

    成功 = all(成功状态) and 日志成功
    print("预渲染全部成功" if 成功 else "预渲染存在失败项目")
    return 成功


def 启动预渲染模式():
    return asyncio.run(执行预渲染())


def 等待预渲染结束(成功):
    """成功时展示结果 5 秒；失败时保留控制台，便于查看错误。"""
    if 成功:
        print("预渲染成功，5 秒后自动退出……")
        time.sleep(5)
        return

    print("预渲染失败，窗口将保持打开；按 Ctrl+C 退出。")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n已退出预渲染窗口。")
