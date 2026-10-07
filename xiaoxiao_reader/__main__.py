"""命令行入口；只有启动时才初始化配置、设备和全局快捷键。"""
import argparse
import asyncio
import traceback
from .platform import 初始化平台


def main():
    parser = argparse.ArgumentParser(description="晓晓朗读（Windows）")
    parser.add_argument("mode", nargs="?", choices=("预渲染",), help="读取剪贴板，批量生成缓存后退出")
    args = parser.parse_args()
    初始化平台()
    from .runtime import 初始化运行环境
    try:
        初始化运行环境()
    except ValueError as exc:
        parser.exit(1, f"配置错误：{exc}\n")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.mode == "预渲染":
        from .prerender import 启动预渲染模式, 等待预渲染结束
        try:
            success = 启动预渲染模式()
        except Exception:
            success = False
            traceback.print_exc()
        等待预渲染结束(success)
        return 0 if success else 1
    import pygame
    pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    try:
        from .app import 启动常驻模式
        启动常驻模式()
    except ValueError as exc:
        parser.exit(1, f"配置错误：{exc}\n")
    finally:
        pygame.mixer.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
