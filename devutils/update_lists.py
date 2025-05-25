#!/usr/bin/env python3

# Copyright (c) 2019 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
自动更新二进制修剪和域名替换列表的工具

该工具会根据需要下载并解压到源码树中。
处理完成后，不会对源码树应用二进制修剪或域名替换。
"""

import argparse
import os
import sys
from itertools import repeat
from multiprocessing import Pool
from pathlib import Path, PurePosixPath
from typing import Set, Tuple, Optional, List, Iterator, Union
import re

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'utils'))
from _common import get_logger
from domain_substitution import DomainRegexList, TREE_ENCODINGS
from prune_binaries import CONTINGENT_PATHS
sys.path.pop(0)

# 输出文件编码
_ENCODING = 'UTF-8'

# 包含模式优先于排除模式
# 要包含在二进制修剪中的pathlib.Path.match()路径
PRUNING_INCLUDE_PATTERNS = [
    'components/domain_reliability/baked_in_configs/*',
    # 为patches/core/ungoogled-chromium/remove-unused-preferences-fields.patch移除
    'components/safe_browsing/core/common/safe_browsing_prefs.cc',
    'components/safe_browsing/core/common/safe_browsing_prefs.h',
    'components/signin/public/base/signin_pref_names.cc',
    'components/signin/public/base/signin_pref_names.h',
]

# 要从二进制修剪中排除的pathlib.Path.match()路径
PRUNING_EXCLUDE_PATTERNS = [
    'chrome/common/win/eventlog_messages.mc',  # 待修复：误报文本文件
    # DOM蒸馏器排除项（仅包含模型数据）
    'components/dom_distiller/core/data/distillable_page_model_new.bin',
    'components/dom_distiller/core/data/long_page_model.bin',
    # 地理语言数据排除项
    'components/language/content/browser/ulp_language_code_locator/geolanguage-data_rank0.bin',
    'components/language/content/browser/ulp_language_code_locator/geolanguage-data_rank1.bin',
    'components/language/content/browser/ulp_language_code_locator/geolanguage-data_rank2.bin',
    # Windows arm64构建所需的预构建对象排除项
    'third_party/crashpad/crashpad/util/misc/capture_context_win_arm64.obj',
    'third_party/icu/common/icudtl.dat',  # ICU数据排除项
    # Android排除项
    'build/android/chromium-debug.keystore',
    'third_party/icu/android/icudtl.dat',
    'third_party/icu/common/icudtb.dat',
    # rollup v4.0+排除项
    'third_party/devtools-frontend/src/node_modules/@rollup/wasm-node/dist/wasm-node/bindings_wasm_bg.wasm',
    'third_party/node/node_modules/@rollup/wasm-node/dist/wasm-node/bindings_wasm_bg.wasm',
    # 性能跟踪排除项
    'third_party/perfetto/src/trace_processor/importers/proto/atoms.descriptor',
    # 安全文件扩展名排除项
    '*.avif', '*.ttf', '*.png', '*.jpg', '*.webp', '*.gif', '*.ico',
    '*.mp3', '*.wav', '*.flac', '*.icns', '*.woff', '*.woff2',
    '*makefile', '*.profdata', '*.xcf', '*.cur', '*.pdf', '*.ai',
    '*.h', '*.c', '*.cpp', '*.cc', '*.mk', '*.bmp', '*.py',
    '*.xml', '*.html', '*.js', '*.json', '*.txt', '*.xtb'
]

# 域名替换路径前缀排除优先于包含模式
# 用于域名替换的POSIX表示前缀排除路径
DOMAIN_EXCLUDE_PREFIXES = [
    'components/test/',
    'net/http/transport_security_state_static.json',
    'net/http/transport_security_state_static_pins.json',
    # 使用GN生成Visual Studio项目的排除项（PR #445）
    'tools/gn/',
    # 由其他补丁覆盖/不必要的文件排除项
    'third_party/search_engines_data/resources/definitions/prepopulated_engines.json',
    'third_party/blink/renderer/core/dom/document.cc',
    # 允许下载sysroots的排除项
    'build/linux/sysroot_scripts/sysroots.json',
]

# 要包含在域名替换中的pathlib.Path.match()模式
DOMAIN_INCLUDE_PATTERNS = [
    '*.h', '*.hh', '*.hpp', '*.hxx', '*.cc', '*.cpp', '*.cxx', '*.c',
    '*.json', '*.js', '*.html', '*.htm', '*.css', '*.py*', '*.grd*',
    '*.sql', '*.idl', '*.mk', '*.gyp*', 'makefile', '*.ts', '*.txt',
    '*.xml', '*.mm', '*.jinja*', '*.gn', '*.gni'
]

# 二进制检测常量
_TEXTCHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})


class UnusedPatterns:
    """跟踪未使用的前缀和模式"""

    _all_names = (
        'pruning_include_patterns', 'pruning_exclude_patterns',
        'domain_include_patterns', 'domain_exclude_prefixes'
    )

    def __init__(self):
        """初始化所有跟踪的模式和前缀集合"""
        # 用户将丢弃已使用的元素
        for name in self._all_names:
            pattern_list = globals()[name.upper()]
            setattr(self, name, set(pattern_list))

    def log_unused(self, error: bool = True) -> bool:
        """
        记录未使用的模式和前缀
        
        Args:
            error: 是否作为错误级别记录
            
        Returns:
            如果存在未使用的模式或前缀返回True；否则返回False
        """
        have_unused = False
        logger = get_logger()
        log_func = logger.error if error else logger.info
        
        for name in self._all_names:
            current_set = getattr(self, name, None)
            if current_set:
                log_func(f'未使用的{name.upper()}: {current_set}')
                have_unused = True
        return have_unused


def _is_binary(bytes_data: bytes) -> bool:
    """
    判断数据是否为二进制数据（即非人类可读）
    
    Args:
        bytes_data: 要检查的字节数据
        
    Returns:
        如果数据似乎是二进制数据返回True；否则返回False
    """
    # 来源: https://stackoverflow.com/a/7392391
    return bool(bytes_data.translate(None, _TEXTCHARS))


def _dir_empty(path: Union[Path, str]) -> bool:
    """
    判断目录是否为空
    
    Args:
        path: 要测试的目录路径
        
    Returns:
        如果目录为空返回True；否则返回False
    """
    try:
        next(os.scandir(str(path)))
        return False
    except StopIteration:
        return True
    except (OSError, IOError):
        # 如果无法扫描目录，假设它不为空
        return False


def should_prune(path: Path, relative_path: Path, 
                used_pep_set: Set[str], used_pip_set: Set[str]) -> bool:
    """
    判断路径是否应该从源码树中修剪
    
    Args:
        path: 从当前工作目录到文件的pathlib.Path
        relative_path: 从源码树到文件的pathlib.Path
        used_pep_set: 已匹配的PRUNING_EXCLUDE_PATTERNS列表
        used_pip_set: 已匹配的PRUNING_INCLUDE_PATTERNS列表
        
    Returns:
        如果应该修剪路径返回True；否则返回False
    """
    # 匹配包含模式
    for pattern in PRUNING_INCLUDE_PATTERNS:
        if relative_path.match(pattern):
            used_pip_set.add(pattern)
            return True

    # 匹配排除模式
    relative_lower = Path(str(relative_path).lower())
    for pattern in PRUNING_EXCLUDE_PATTERNS:
        if relative_lower.match(pattern):
            used_pep_set.add(pattern)
            return False

    # 执行二进制数据检测
    try:
        with path.open('rb') as file_obj:
            chunk = file_obj.read(8192)  # 读取前8KB进行检测
            if not chunk:
                # 空文件视为文本文件
                return False
            return _is_binary(chunk)
    except (IOError, OSError) as e:
        get_logger().warning(f'无法读取文件{path}进行二进制检测: {e}')
        return False


def _check_regex_match(file_path: Path, search_regex: re.Pattern[str]) -> bool:
    """
    检查文件是否包含正则表达式匹配
    
    Args:
        file_path: 要检查的文件路径
        search_regex: 编译的正则表达式
        
    Returns:
        如果文件包含匹配返回True；否则返回False
    """
    try:
        with file_path.open('rb') as file_obj:
            content = file_obj.read()
            
        # 尝试不同编码解码内容
        for encoding in TREE_ENCODINGS:
            try:
                text_content = content.decode(encoding)
                if search_regex.search(text_content):
                    return True
                break
            except UnicodeDecodeError:
                continue
        else:
            # 无法解码，可能是二进制文件
            return False
            
    except (IOError, OSError) as e:
        get_logger().warning(f'检查正则表达式匹配时无法读取文件{file_path}: {e}')
        
    return False


def should_domain_substitute(path: Path, relative_path: Path, search_regex: re.Pattern[str],
                           used_dep_set: Set[str], used_dip_set: Set[str]) -> bool:
    """
    判断路径是否应该进行域名替换
    
    Args:
        path: 从当前工作目录到文件的pathlib.Path
        relative_path: 从源码树到文件的pathlib.Path
        search_regex: 编译的搜索正则表达式
        used_dep_set: 已匹配的DOMAIN_EXCLUDE_PREFIXES列表
        used_dip_set: 已匹配的DOMAIN_INCLUDE_PATTERNS列表
        
    Returns:
        如果应该进行域名替换返回True；否则返回False
    """
    relative_posix = relative_path.as_posix()
    
    # 检查排除前缀
    for prefix in DOMAIN_EXCLUDE_PREFIXES:
        if relative_posix.startswith(prefix):
            used_dep_set.add(prefix)
            return False
    
    # 检查包含模式
    for pattern in DOMAIN_INCLUDE_PATTERNS:
        if relative_path.match(pattern):
            used_dip_set.add(pattern)
            # 检查文件是否包含域名匹配
            return _check_regex_match(path, search_regex)
    
    return False


def compute_lists_proc(path: Path, source_tree: Path, search_regex: re.Pattern[str]) -> Tuple[
    Optional[str], Optional[str], Set[str], Set[str], Set[str], Set[str]
]:
    """
    为单个路径计算列表的进程函数
    
    Args:
        path: 文件的绝对路径
        source_tree: 源码树根目录路径
        search_regex: 域名搜索的编译正则表达式
        
    Returns:
        (修剪路径, 域名替换路径, 使用的修剪排除模式, 使用的修剪包含模式,
         使用的域名排除前缀, 使用的域名包含模式)的元组
    """
    try:
        relative_path = path.relative_to(source_tree)
    except ValueError:
        # 路径不在源码树中
        return None, None, set(), set(), set(), set()
    
    used_pep_set = set()
    used_pip_set = set()
    used_dep_set = set()
    used_dip_set = set()
    
    prune_path = None
    domain_path = None
    
    if should_prune(path, relative_path, used_pep_set, used_pip_set):
        prune_path = relative_path.as_posix()
    
    if should_domain_substitute(path, relative_path, search_regex, used_dep_set, used_dip_set):
        domain_path = relative_path.as_posix()
    
    return prune_path, domain_path, used_pep_set, used_pip_set, used_dep_set, used_dip_set


def compute_lists(source_tree: Path, search_regex: re.Pattern[str], 
                 processes: int) -> Tuple[List[str], List[str], UnusedPatterns]:
    """
    计算修剪和域名替换列表
    
    Args:
        source_tree: 源码树根目录路径
        search_regex: 域名搜索的编译正则表达式
        processes: 要使用的进程数
        
    Returns:
        (修剪路径列表, 域名替换路径列表, 未使用模式)的元组
    """
    logger = get_logger()
    logger.info('计算修剪和域名替换列表...')
    
    # 收集所有文件路径
    file_paths = []
    for root, dirs, files in os.walk(source_tree):
        # 过滤空目录
        dirs[:] = [d for d in dirs if not _dir_empty(Path(root) / d)]
        
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.is_file():
                file_paths.append(file_path)
    
    logger.info(f'发现{len(file_paths)}个文件')
    
    # 并行处理文件
    unused_patterns = UnusedPatterns()
    prune_paths = []
    domain_paths = []
    
    if processes == 1:
        # 单进程处理
        for file_path in file_paths:
            result = compute_lists_proc(file_path, source_tree, search_regex)
            prune_path, domain_path, used_pep, used_pip, used_dep, used_dip = result
            
            if prune_path:
                prune_paths.append(prune_path)
            if domain_path:
                domain_paths.append(domain_path)
                
            # 更新已使用的模式
            unused_patterns.pruning_exclude_patterns -= used_pep
            unused_patterns.pruning_include_patterns -= used_pip
            unused_patterns.domain_exclude_prefixes -= used_dep
            unused_patterns.domain_include_patterns -= used_dip
    else:
        # 多进程处理
        with Pool(processes=processes) as pool:
            results = pool.starmap(
                compute_lists_proc,
                zip(file_paths, repeat(source_tree), repeat(search_regex))
            )
        
        for result in results:
            prune_path, domain_path, used_pep, used_pip, used_dep, used_dip = result
            
            if prune_path:
                prune_paths.append(prune_path)
            if domain_path:
                domain_paths.append(domain_path)
                
            # 更新已使用的模式
            unused_patterns.pruning_exclude_patterns -= used_pep
            unused_patterns.pruning_include_patterns -= used_pip
            unused_patterns.domain_exclude_prefixes -= used_dep
            unused_patterns.domain_include_patterns -= used_dip
    
    # 排序结果
    prune_paths.sort()
    domain_paths.sort()
    
    logger.info(f'找到{len(prune_paths)}个要修剪的路径')
    logger.info(f'找到{len(domain_paths)}个要进行域名替换的路径')
    
    return prune_paths, domain_paths, unused_patterns


def main(args_list: Optional[List[str]] = None) -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='更新二进制修剪和域名替换列表')
    parser.add_argument(
        'source_tree', type=Path,
        help='包含要扫描文件的源码树目录'
    )
    parser.add_argument(
        'domain_regex_file', type=Path,
        help='包含域名正则表达式的文件路径'
    )
    parser.add_argument(
        '--output-pruning', type=Path, default=Path('pruning.list'),
        help='输出修剪列表文件路径（默认：pruning.list）'
    )
    parser.add_argument(
        '--output-domain', type=Path, default=Path('domain_substitution.list'),
        help='输出域名替换列表文件路径（默认：domain_substitution.list）'
    )
    parser.add_argument(
        '--processes', type=int, default=os.cpu_count(),
        help=f'要使用的进程数（默认：{os.cpu_count()}）'
    )
    parser.add_argument(
        '--show-unused', action='store_true',
        help='显示未使用的模式（作为信息而非错误）'
    )
    
    args = parser.parse_args(args_list)
    logger = get_logger()
    
    # 验证输入
    if not args.source_tree.exists():
        logger.error(f'源码树目录不存在: {args.source_tree}')
        sys.exit(1)
    
    if not args.domain_regex_file.exists():
        logger.error(f'域名正则表达式文件不存在: {args.domain_regex_file}')
        sys.exit(1)
    
    try:
        # 加载域名正则表达式
        domain_regex_list = DomainRegexList(args.domain_regex_file)
        search_regex = domain_regex_list.search_regex
        
        # 计算列表
        prune_paths, domain_paths, unused_patterns = compute_lists(
            args.source_tree, search_regex, args.processes
        )
        
        # 写入修剪列表
        with args.output_pruning.open('w', encoding=_ENCODING) as f:
            f.write('\n'.join(prune_paths))
        logger.info(f'修剪列表已写入: {args.output_pruning}')
        
        # 写入域名替换列表
        with args.output_domain.open('w', encoding=_ENCODING) as f:
            f.write('\n'.join(domain_paths))
        logger.info(f'域名替换列表已写入: {args.output_domain}')
        
        # 报告未使用的模式
        if unused_patterns.log_unused(error=not args.show_unused):
            if not args.show_unused:
                logger.warning('存在未使用的模式，请检查配置')
        else:
            logger.info('所有模式都已使用')
            
    except Exception as e:
        logger.error(f'处理失败: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
