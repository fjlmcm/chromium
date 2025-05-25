# -*- coding: UTF-8 -*-

# Copyright (c) 2020 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""通用代码和常量模块"""

import argparse
import enum
import logging
import platform
from pathlib import Path
from typing import Iterator, Optional, Any, Union


# 常量定义
ENCODING = 'UTF-8'  # 配置文件和补丁的编码
USE_REGISTRY = '_use_registry'
LOGGER_NAME = 'ungoogled'


class PlatformEnum(enum.Enum):
    """支持平台的枚举类型"""
    UNIX = 'unix'       # 目前覆盖所有非Windows系统
    WINDOWS = 'windows'


class ExtractorEnum(enum.Enum):
    """提取工具的枚举类型"""
    SEVENZIP = '7z'
    TAR = 'tar'
    WINRAR = 'winrar'


class SetLogLevel(argparse.Action):
    """根据命令行参数设置日志级别的动作类"""
    
    def __init__(self, option_strings: list, dest: str, nargs: Optional[str] = None, **kwargs):
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, 
                 value: Any, option_string: Optional[str] = None) -> None:
        """设置对应的日志级别"""
        level_mapping = {
            ('--verbose', '-v'): logging.DEBUG,
            ('--quiet', '-q'): logging.ERROR,
        }
        
        # 检查是否是预定义的选项
        for options, level in level_mapping.items():
            if option_string in options:
                value = level
                break
        else:
            # 处理明确指定的日志级别
            level_names = {
                'FATAL': logging.FATAL,
                'ERROR': logging.ERROR,
                'WARNING': logging.WARNING,
                'INFO': logging.INFO,
                'DEBUG': logging.DEBUG
            }
            value = level_names.get(value, logging.INFO)
        
        set_logging_level(value)


def get_logger(initial_level: int = logging.INFO) -> logging.Logger:
    """获取命名日志记录器
    
    Args:
        initial_level: 初始日志级别
        
    Returns:
        配置好的日志记录器实例
    """
    logger = logging.getLogger(LOGGER_NAME)

    if logger.level == logging.NOTSET:
        logger.setLevel(initial_level)

        if not logger.hasHandlers():
            console_handler = logging.StreamHandler()
            console_handler.setLevel(initial_level)

            formatter = logging.Formatter('%(levelname)s: %(message)s')
            console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)
    
    return logger


def set_logging_level(logging_level: int) -> logging.Logger:
    """设置日志记录器及其所有处理器的日志级别
    
    Args:
        logging_level: 要设置的日志级别
        
    Returns:
        更新后的日志记录器
    """
    if not logging_level:
        logging_level = logging.INFO

    logger = get_logger()
    logger.setLevel(logging_level)

    if logger.hasHandlers():
        for handler in logger.handlers:
            handler.setLevel(logging_level)

    return logger


def get_running_platform() -> PlatformEnum:
    """获取当前运行平台
    
    注意：平台检测应仅在没有跨平台替代方案时使用
    
    Returns:
        表示当前平台的PlatformEnum值
    """
    uname = platform.uname()
    
    # 检测原生Python和WSL
    if uname.system == 'Windows' or 'Microsoft' in uname.release:
        return PlatformEnum.WINDOWS
    
    # 目前只需要区分Windows和基于UNIX的平台
    return PlatformEnum.UNIX


def get_chromium_version() -> str:
    """获取Chromium版本号
    
    Returns:
        Chromium版本字符串
    """
    version_file = Path(__file__).parent.parent / 'chromium_version.txt'
    return version_file.read_text(encoding=ENCODING).strip()


def parse_series(series_path: Path) -> Iterator[str]:
    """解析系列文件并返回路径迭代器
    
    Args:
        series_path: 系列文件的路径
        
    Yields:
        系列文件中的路径字符串
    """
    try:
        with series_path.open(encoding=ENCODING) as series_file:
            series_lines = series_file.read().splitlines()
    except (FileNotFoundError, IOError) as e:
        get_logger().error(f"无法读取系列文件 {series_path}: {e}")
        return

    # 过滤处理
    series_lines = filter(len, series_lines)  # 过滤空行
    series_lines = filter(lambda x: not x.startswith('#'), series_lines)  # 过滤注释行
    series_lines = map(lambda x: x.strip().split(' #')[0], series_lines)  # 去除行内注释
    
    yield from series_lines


def add_common_params(parser: argparse.ArgumentParser) -> None:
    """为解析器添加通用的命令行参数
    
    Args:
        parser: 要添加参数的ArgumentParser实例
    """
    # 日志级别组
    logging_group = parser.add_mutually_exclusive_group()
    
    logging_group.add_argument(
        '--log-level',
        action=SetLogLevel,
        choices=['FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
        help="设置当前脚本的日志级别。'log-level'、'verbose'、'quiet' 只能同时设置一个。"
    )
    
    logging_group.add_argument(
        '--quiet', '-q',
        action=SetLogLevel,
        nargs=0,
        help="减少控制台输出。'log-level'、'verbose'、'quiet' 只能同时设置一个。"
    )
    
    logging_group.add_argument(
        '--verbose', '-v',
        action=SetLogLevel,
        nargs=0,
        help="增加日志详细程度以包含DEBUG消息。'log-level'、'verbose'、'quiet' 只能同时设置一个。"
    )
