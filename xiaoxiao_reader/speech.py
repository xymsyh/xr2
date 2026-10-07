"""语音缓存播放、在线合成及可选音频发送。"""
import os
import io
import asyncio
import pygame
import edge_tts
import requests
from . import runtime
from .text import 选择朗读语音
from .storage import 语音缓存键, 语音缓存文件路径, _写入语音缓存

当前音频缓冲 = None


def 发送朗读音频(音频字节):
    """在后台线程中把已合成的 MP3 发送到配置的网址，不影响本地播放。"""
    try:
        with requests.Session() as 会话:
            # 不读取系统代理设置，避免本机代理不支持 HTTPS 时干扰发送。
            会话.trust_env = False
            响应 = 会话.post(
                runtime.音频发送地址,
                headers={
                    "Content-Type": "audio/mpeg",
                    "X-Filename": "notice.mp3",
                },
                data=音频字节,
                timeout=(5, 30),
            )
            响应.raise_for_status()
        print(f"音频已发送：{runtime.音频发送地址}")
    except Exception as e:
        print("音频发送失败：", e)


async def 朗读文本(文本):
    global 当前音频缓冲

    print("\n正在朗读：", 文本)

    循环 = asyncio.get_event_loop()
    使用语音 = 选择朗读语音(文本)
    键 = 语音缓存键(文本, 使用语音)
    缓存路径, 文件名 = 语音缓存文件路径(键)

    try:
        音频 = None

        # 先查本地语音缓存：命中就直接读文件播放，完全跳过 edge-tts 的网络合成，
        # 这是"选中→出声"延迟的主要来源，命中缓存基本是毫秒级出声
        if os.path.isfile(缓存路径):
            try:
                with open(缓存路径, "rb") as f:
                    音频 = f.read()
                print("命中语音缓存，跳过 TTS 合成")
            except Exception as e:
                print("读取语音缓存失败，将重新合成：", e)
                音频 = None

        if not 音频:
            音频字节 = bytearray()
            communicate = edge_tts.Communicate(text=文本, voice=使用语音)

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    音频字节.extend(chunk["data"])

            if not 音频字节:
                print("语音生成失败：未收到音频数据")
                return

            音频 = bytes(音频字节)

            # 写盘放到线程池执行，不等待其完成，不拖慢本次播放
            循环.run_in_executor(None, _写入语音缓存, 键, 文件名, 缓存路径, 文本, 音频)

        pygame.mixer.music.stop()
        当前音频缓冲 = io.BytesIO(音频)
        pygame.mixer.music.load(当前音频缓冲, "mp3")
        pygame.mixer.music.play()
        print("正在播放……")

        if runtime.音频发送启用:
            循环.run_in_executor(None, 发送朗读音频, 音频)

    except asyncio.CancelledError:
        print("\n（朗读已被新的操作取消）")
        raise

    except Exception as e:
        print("\n朗读失败：", e)
