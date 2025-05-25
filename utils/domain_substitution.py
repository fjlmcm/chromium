#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (c) 2019 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
在源码树中替换域名为可阻止的字符串
"""

import argparse
import collections
import contextlib
import io
import os
import re
import stat
import tarfile
import tempfile
import zlib
from pathlib import Path
from typing import Iterator, Optional, Tuple, Set, NamedTuple

from _extraction import extract_tar_file
from _common import ENCODING, get_logger, add_common_params

# 源码树文件尝试的编码格式
TREE_ENCODINGS = ('UTF-8', 'ISO-8859-1')

# 域名替换缓存常量
_INDEX_LIST = 'cache_index.list'
_INDEX_HASH_DELIMITER = '|'
_ORIG_DIR = 'orig'

# 时间戳操作常量
# 所有文件时间戳之间的增量（纳秒）
_TIMESTAMP_DELTA = 1 * 10**9


class DomainRegexPair(NamedTuple):
    """域名正则表达式对"""
    pattern: re.Pattern[str]
    replacement: str


class DomainRegexList:
    """域名正则表达式列表文件的表示"""
    
    # 格式常量
    _PATTERN_REPLACE_DELIM = '#'

    def __init__(self, path: Path):
        """初始化域名正则表达式列表
        
        Args:
            path: domain_regex.list文件的路径
        """
        self._data = tuple(filter(len, path.read_text(encoding=ENCODING).splitlines()))
        # 编译正则表达式对的缓存
        self._compiled_regex: Optional[Tuple[DomainRegexPair, ...]] = None

    def _compile_regex(self, line: str) -> DomainRegexPair:
        """为给定行生成正则表达式对元组
        
        Args:
            line: 包含模式和替换的行
            
        Returns:
            编译后的正则表达式对
            
        Raises:
            ValueError: 如果行格式不正确
        """
        try:
            pattern, replacement = line.split(self._PATTERN_REPLACE_DELIM, 1)
            return DomainRegexPair(re.compile(pattern), replacement)
        except ValueError as e:
            raise ValueError(f"无效的正则表达式行格式: {line}") from e

    @property
    def regex_pairs(self) -> Tuple[DomainRegexPair, ...]:
        """返回编译后的正则表达式对元组"""
        if self._compiled_regex is None:
            self._compiled_regex = tuple(self._compile_regex(line) for line in self._data)
        return self._compiled_regex

    @property
    def search_regex(self) -> re.Pattern[str]:
        """返回用于搜索域名的单一表达式"""
        patterns = [line.split(self._PATTERN_REPLACE_DELIM, 1)[0] for line in self._data]
        return re.compile('|'.join(patterns))


def _substitute_path(path: Path, regex_iter: Iterator[DomainRegexPair]) -> Tuple[Optional[int], Optional[bytes]]:
    """
    对路径执行域名替换并将其添加到域名替换缓存
    
    Args:
        path: 要进行域名替换的文件路径
        regex_iter: 正则表达式对的可迭代对象
        
    Returns:
        (替换后原始内容的CRC32哈希, 原始原始内容)的元组；
        如果没有进行替换，则两个条目都为None
        
    Raises:
        FileNotFoundError: 如果路径不存在
        UnicodeDecodeError: 如果路径内容无法解码
    """
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
        
    # 如果补丁无法写入，则无法打开进行更新
    if not os.access(path, os.W_OK):
        get_logger().info(f"文件 {path} 无法写入！正在添加写权限...")
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
        
    with path.open('r+b') as input_file:
        original_content = input_file.read()
        if not original_content:
            return (None, None)
            
        # 尝试不同编码解码内容
        content = None
        encoding = None
        for encoding in TREE_ENCODINGS:
            try:
                content = original_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if content is None:
            raise UnicodeDecodeError(f'无法使用任何编码解码: {path}')
            
        # 执行替换
        file_subs = 0
        for regex_pair in regex_iter:
            content, sub_count = regex_pair.pattern.subn(regex_pair.replacement, content)
            file_subs += sub_count
            
        if file_subs > 0:
            substituted_content = content.encode(encoding)
            input_file.seek(0)
            input_file.write(substituted_content)
            input_file.truncate()
            return (zlib.crc32(substituted_content), original_content)
            
        return (None, None)


def _validate_file_index(index_file: io.BufferedReader, resolved_tree: Path, 
                        cache_index_files: Set[str]) -> bool:
    """
    验证文件索引和哈希对源码树的有效性，更新cache_index_files
    
    Args:
        index_file: 索引文件句柄
        resolved_tree: 解析后的源码树路径
        cache_index_files: 缓存索引文件集合
        
    Returns:
        如果文件索引有效返回True；否则返回False
    """
    all_hashes_valid = True
    crc32_regex = re.compile(r'^[a-zA-Z0-9]{8}$')
    
    try:
        content = index_file.read().decode(ENCODING)
    except UnicodeDecodeError as e:
        get_logger().error(f"无法解码索引文件: {e}")
        return False
        
    for entry in content.splitlines():
        try:
            relative_path, file_hash = entry.split(_INDEX_HASH_DELIMITER, 1)
        except ValueError as exc:
            get_logger().error(f'无法分割条目 "{entry}": {exc}')
            continue
            
        if not relative_path or not file_hash:
            get_logger().error(f'域名替换缓存文件索引条目无效: {entry}')
            all_hashes_valid = False
            continue
            
        if not crc32_regex.match(file_hash):
            get_logger().error(f'文件 {relative_path} 的索引哈希似乎不是CRC32哈希')
            all_hashes_valid = False
            continue
            
        try:
            file_path = resolved_tree / relative_path
            if not file_path.exists():
                get_logger().error(f'文件不存在: {relative_path}')
                all_hashes_valid = False
                continue
                
            actual_hash = zlib.crc32(file_path.read_bytes())
            expected_hash = int(file_hash, 16)
            
            if actual_hash != expected_hash:
                get_logger().error(f'哈希不匹配: {relative_path}')
                all_hashes_valid = False
                continue
                
        except (IOError, ValueError) as e:
            get_logger().error(f'验证文件 {relative_path} 时出错: {e}')
            all_hashes_valid = False
            continue
            
        if relative_path in cache_index_files:
            get_logger().error(f'文件 {relative_path} 在文件索引中至少出现两次')
            all_hashes_valid = False
            continue
            
        cache_index_files.add(relative_path)
        
    return all_hashes_valid


@contextlib.contextmanager
def _update_timestamp(path: os.PathLike, set_new: bool):
    """
    设置路径时间戳的上下文管理器，无论上下文内的修改如何，
    都会在固定增量上加减
    
    Args:
        path: 要更新时间戳的路径
        set_new: 如果为True，增加增量；否则减去增量
    """
    try:
        stats = os.stat(path)
        if set_new:
            new_timestamp = (
                stats.st_atime_ns + _TIMESTAMP_DELTA, 
                stats.st_mtime_ns + _TIMESTAMP_DELTA
            )
        else:
            new_timestamp = (
                stats.st_atime_ns - _TIMESTAMP_DELTA, 
                stats.st_mtime_ns - _TIMESTAMP_DELTA
            )
        
        yield
        
    finally:
        os.utime(path, ns=new_timestamp)


def apply_substitution(regex_path: Path, files_path: Path, source_tree: Path, 
                      domainsub_cache: Path) -> None:
    """
    在源码树中替换域名并保存替换前的存档
    
    Args:
        regex_path: domain_regex.list的路径
        files_path: domain_substitution.list的路径
        source_tree: 源码树的路径
        domainsub_cache: 域名替换缓存的路径
        
    Raises:
        NotADirectoryError: 如果补丁目录不是目录或不存在
        FileNotFoundError: 如果源码树或所需目录不存在
        FileExistsError: 如果域名替换缓存已存在
        ValueError: 如果域名替换列表中的条目包含文件索引哈希分隔符
    """
    logger = get_logger()
    
    # 验证输入路径
    if not source_tree.exists():
        raise FileNotFoundError(f"源码树不存在: {source_tree}")
    if not regex_path.exists():
        raise FileNotFoundError(f"正则表达式文件不存在: {regex_path}")
    if not files_path.exists():
        raise FileNotFoundError(f"文件列表不存在: {files_path}")
    if domainsub_cache.exists():
        raise FileExistsError(f"域名替换缓存已存在: {domainsub_cache}")
        
    logger.info('应用域名替换...')
    
    # 读取域名正则表达式
    domain_regex_list = DomainRegexList(regex_path)
    
    # 读取要替换的文件列表
    try:
        files_under_domsub = files_path.read_text(encoding=ENCODING).splitlines()
    except IOError as e:
        raise FileNotFoundError(f"无法读取文件列表: {e}") from e
        
    # 过滤空行和注释
    files_under_domsub = [line.strip() for line in files_under_domsub if line.strip() and not line.strip().startswith('#')]
    
    # 验证文件路径不包含哈希分隔符
    for file_path_str in files_under_domsub:
        if _INDEX_HASH_DELIMITER in file_path_str:
            raise ValueError(f'域名替换列表条目包含哈希分隔符: {file_path_str}')
    
    # 创建缓存目录
    domainsub_cache.mkdir(parents=True)
    orig_dir = domainsub_cache / _ORIG_DIR
    orig_dir.mkdir()
    
    # 执行替换并创建缓存
    files_hit = []
    for file_path_str in files_under_domsub:
        file_path = source_tree / file_path_str
        
        if not file_path.exists():
            logger.warning(f"文件不存在，跳过: {file_path_str}")
            continue
            
        try:
            crc32_hash, original_content = _substitute_path(file_path, domain_regex_list.regex_pairs)
            
            if crc32_hash is not None and original_content is not None:
                # 保存原始内容
                orig_file_path = orig_dir / file_path_str
                orig_file_path.parent.mkdir(parents=True, exist_ok=True)
                orig_file_path.write_bytes(original_content)
                
                # 记录到索引
                files_hit.append(f"{file_path_str}{_INDEX_HASH_DELIMITER}{crc32_hash:08x}")
                
        except (UnicodeDecodeError, IOError) as e:
            logger.error(f"处理文件 {file_path_str} 时出错: {e}")
            continue
    
    # 写入索引文件
    index_file_path = domainsub_cache / _INDEX_LIST
    with index_file_path.open('w', encoding=ENCODING) as index_file:
        index_file.write('\n'.join(files_hit))
    
    logger.info(f'域名替换完成，处理了 {len(files_hit)} 个文件')


def revert_substitution(domainsub_cache: Path, source_tree: Path) -> None:
    """
    从域名替换缓存恢复文件
    
    Args:
        domainsub_cache: 域名替换缓存的路径
        source_tree: 源码树的路径
        
    Raises:
        FileNotFoundError: 如果缓存或源码树不存在
        ValueError: 如果缓存无效
    """
    logger = get_logger()
    
    if not domainsub_cache.exists():
        raise FileNotFoundError(f"域名替换缓存不存在: {domainsub_cache}")
    if not source_tree.exists():
        raise FileNotFoundError(f"源码树不存在: {source_tree}")
        
    logger.info('恢复域名替换...')
    
    # 验证缓存
    resolved_tree = source_tree.resolve()
    cache_index_files = set()
    
    index_file_path = domainsub_cache / _INDEX_LIST
    if not index_file_path.exists():
        raise ValueError(f"缓存索引文件不存在: {index_file_path}")
        
    with index_file_path.open('rb') as index_file:
        if not _validate_file_index(index_file, resolved_tree, cache_index_files):
            raise ValueError("域名替换缓存验证失败")
    
    # 恢复文件
    orig_dir = domainsub_cache / _ORIG_DIR
    restored_count = 0
    
    for relative_path in cache_index_files:
        orig_file_path = orig_dir / relative_path
        dest_file_path = source_tree / relative_path
        
        if not orig_file_path.exists():
            logger.warning(f"原始文件不存在，跳过: {relative_path}")
            continue
            
        try:
            # 恢复原始内容
            dest_file_path.write_bytes(orig_file_path.read_bytes())
            restored_count += 1
            
        except IOError as e:
            logger.error(f"恢复文件 {relative_path} 时出错: {e}")
            continue
    
    logger.info(f'域名替换恢复完成，恢复了 {restored_count} 个文件')


def _callback(args: argparse.Namespace) -> None:
    """命令行回调函数"""
    if hasattr(args, 'revert') and args.revert:
        revert_substitution(args.cache_dir, args.source_tree)
    else:
        apply_substitution(args.regex_list, args.files_list, args.source_tree, args.cache_dir)


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='域名替换工具')
    add_common_params(parser)
    
    parser.add_argument('regex_list', type=Path, help='域名正则表达式列表文件路径')
    parser.add_argument('files_list', type=Path, help='要替换的文件列表路径')
    parser.add_argument('source_tree', type=Path, help='源码树路径')
    parser.add_argument('cache_dir', type=Path, help='域名替换缓存目录路径')
    parser.add_argument('--revert', action='store_true', help='恢复域名替换')
    
    args = parser.parse_args()
    _callback(args)


if __name__ == '__main__':
    main()
