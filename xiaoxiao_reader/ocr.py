"""懒加载本地 OCR 引擎，截图只在内存中处理。"""
import io
import threading
OCR引擎 = None
OCR引擎锁 = threading.Lock()


def 识别截图(截图):
    global OCR引擎
    from rapidocr_onnxruntime import RapidOCR
    # 用 PNG 字节传入，避免 RGB/BGR 通道顺序差异。
    缓冲 = io.BytesIO()
    截图.save(缓冲, format="PNG")
    with OCR引擎锁:
        if OCR引擎 is None:
            OCR引擎 = RapidOCR()
        结果, _ = OCR引擎(缓冲.getvalue())
    return "\n".join(项[1].strip() for 项 in (结果 or []) if 项[1].strip())
