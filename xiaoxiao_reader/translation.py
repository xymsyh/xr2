"""本地词典优先、在线翻译回退及结果通知。"""
import asyncio
import uuid
import requests
from . import runtime
from .runtime import 翻译队列
from .text import 预处理翻译文本
from .storage import 翻译缓存, 缓存键, 保存翻译缓存, 更新翻译记录
from .dictionary import 提取英文单词, 是单词查询, 查询本地词典, 生成记录摘要, 本地词典不可用


def 调用翻译接口(文本, 目标语言="zh-Hans"):
    if not runtime.KEY:
        raise ValueError("请在 config/配置.ini 的 [微软翻译API] 中填写密钥，然后重启程序。")
    headers = {
        "Ocp-Apim-Subscription-Key": runtime.KEY,
        "Ocp-Apim-Subscription-Region": runtime.REGION,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    params = {"api-version": "3.0", "to": [目标语言]}
    body = [{"text": 文本}]

    响应 = requests.post(
        runtime.ENDPOINT,
        params=params,
        headers=headers,
        json=body,
        proxies={"http": None, "https": None},
        timeout=10,
    )
    响应.raise_for_status()
    结果 = 响应.json()
    return 结果[0]["translations"][0]["text"]


async def 翻译并显示(文本):
    try:
        循环 = asyncio.get_event_loop()
        待翻译文本 = 预处理翻译文本(文本)
        键 = 缓存键(待翻译文本)

        # 单个英文词走本地结构化词典，命中时完全不请求翻译 API。
        本地查询失败 = None
        if 是单词查询(文本, 待翻译文本):
            单词 = 提取英文单词(文本)
            try:
                词条 = await 循环.run_in_executor(None, 查询本地词典, 单词)
            except 本地词典不可用 as e:
                本地查询失败 = e
                print("本地词典不可用，将尝试在线翻译：", e)
            else:
                if 词条:
                    print("命中本地词典，跳过 API 调用：", 词条["单词"])
                    翻译队列.put(词条)
                    await 循环.run_in_executor(
                        None, 更新翻译记录, 文本, 待翻译文本, 生成记录摘要(词条),
                        "单词", 词条["单词"], "本地词典",
                    )
                    return

        译文 = 翻译缓存.get(键)
        来自缓存 = 译文 is not None

        if 来自缓存:
            print("命中翻译缓存，跳过 API 调用")
        else:
            if not runtime.KEY:
                if 是单词查询(文本, 待翻译文本) and 本地查询失败 is None:
                    提示 = "本地词典暂未收录该词；在线翻译未配置。朗读仍可使用。"
                elif 本地查询失败 is not None:
                    提示 = f"本地词典不可用：{本地查询失败}；在线翻译也未配置。"
                else:
                    提示 = "在线翻译未配置：请在 config/配置.ini 中填写微软翻译 API 密钥，然后重启。朗读仍可使用。"
                翻译队列.put(提示)
                return
            译文 = await 循环.run_in_executor(None, 调用翻译接口, 待翻译文本)
            翻译缓存[键] = 译文
            await 循环.run_in_executor(None, 保存翻译缓存)

        print("翻译结果：", 译文)
        翻译队列.put({"类型": "在线翻译", "译文": 译文})

        # 无论是否命中缓存，都更新学习记录（相同内容自动合并计数，只保留最新时间）
        await 循环.run_in_executor(None, 更新翻译记录, 文本, 待翻译文本, 译文)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print("翻译失败：", e)
        翻译队列.put("翻译失败，请检查网络、API 配置和服务额度；详情见控制台。")
