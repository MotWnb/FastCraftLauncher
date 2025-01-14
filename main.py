import asyncio
import logging
import os
import downloader
import launcher

# 确保日志目录存在
log_dir = 'FCL/logs'
os.makedirs(log_dir, exist_ok=True)

# 配置日志记录，只输出 INFO 级别及以上的日志，并将日志写入文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "launcher.log")),
        logging.StreamHandler()
    ]
)

async def main():
    action = input("请选择操作（1：下载，2：启动）：")
    if action == '1':
        version = input("请输入Minecraft版本：")
        await downloader.download(version)
    elif action == '2':
        await launcher.launch_game()
    else:
        print("无效的选择")

if __name__ == "__main__":
    asyncio.run(main())