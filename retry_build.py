#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
重试构建脚本 - 自动处理网络错误并重试
"""

import subprocess
import sys
import time
from pathlib import Path

def run_with_retry(cmd, max_retries=3, delay=30):
    """运行命令并在失败时重试"""
    for attempt in range(max_retries):
        try:
            print(f"\n=== 尝试 {attempt + 1}/{max_retries} ===")
            result = subprocess.run(cmd, check=True, shell=True)
            print(f"命令成功执行: {cmd}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"命令失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"等待 {delay} 秒后重试...")
                time.sleep(delay)
            else:
                print("所有重试都失败了")
                raise e

def main():
    """主函数"""
    print("=== Ungoogled Chromium 重试构建脚本 ===")
    
    # 检查是否在正确的目录
    if not Path('build.py').exists():
        print("错误: 请在ungoogled-chromium项目根目录运行此脚本")
        sys.exit(1)
    
    # 清理之前失败的构建
    build_dir = Path('build')
    if build_dir.exists():
        print("清理之前的构建目录...")
        import shutil
        shutil.rmtree(build_dir, ignore_errors=True)
    
    try:
        # 重试构建
        print("\n开始构建...")
        run_with_retry('python build.py', max_retries=3, delay=60)
        
        print("\n开始打包...")
        run_with_retry('python package.py', max_retries=2, delay=30)
        
        print("\n=== 构建完成! ===")
        
    except Exception as e:
        print(f"\n构建失败: {e}")
        print("\n建议:")
        print("1. 检查网络连接")
        print("2. 尝试使用VPN")
        print("3. 手动下载Chromium源码")
        sys.exit(1)

if __name__ == '__main__':
    main()
