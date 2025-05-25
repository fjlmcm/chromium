#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (c) 2020 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""应用统一diff补丁的工具模块"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Iterator, List

from _common import get_logger, parse_series, add_common_params


class PatchError(Exception):
    """补丁相关错误的基类"""
    pass


class PatchNotFoundError(PatchError):
    """找不到补丁工具时抛出的异常"""
    pass


class PatchExecutionError(PatchError):
    """补丁执行失败时抛出的异常"""
    pass


def _find_patch_from_env() -> Optional[Path]:
    """从环境变量中查找补丁工具
    
    Returns:
        补丁工具的路径，如果未找到则返回None
    """
    logger = get_logger()
    patch_bin_env = os.environ.get('PATCH_BIN')
    
    if not patch_bin_env:
        logger.debug('PATCH_BIN环境变量未设置')
        return None
        
    patch_bin_path = Path(patch_bin_env)
    if patch_bin_path.exists():
        logger.debug(f'通过PATCH_BIN找到路径: {patch_bin_path}')
        return patch_bin_path
        
    # 尝试在PATH中查找命令
    patch_which = shutil.which(patch_bin_env)
    if patch_which:
        logger.debug(f'通过PATCH_BIN命令找到路径: {patch_which}')
        return Path(patch_which)
        
    return None


def _find_patch_from_which() -> Optional[Path]:
    """在PATH环境变量中查找patch命令
    
    Returns:
        patch命令的路径，如果未找到则返回None
    """
    patch_which = shutil.which('patch')
    if not patch_which:
        get_logger().debug('在PATH环境变量中未找到"patch"命令')
        return None
    return Path(patch_which)


def find_and_check_patch(patch_bin_path: Optional[Path] = None) -> Path:
    """
    查找并检查补丁工具是否正常工作
    
    查找顺序：
    1. 如果patch_bin_path不为None，则使用它
    2. 检查PATCH_BIN环境变量是否设置
    3. 使用"which patch"查找GNU patch
    
    然后执行一些健全性检查，确认补丁命令有效
    
    Args:
        patch_bin_path: 可选的补丁工具路径
        
    Returns:
        找到的补丁工具路径
        
    Raises:
        PatchNotFoundError: 找不到补丁工具时
        PatchExecutionError: 补丁工具无法正常执行时
    """
    if patch_bin_path is None:
        patch_bin_path = _find_patch_from_env()
    if patch_bin_path is None:
        patch_bin_path = _find_patch_from_which()
        
    if not patch_bin_path:
        raise PatchNotFoundError('无法从PATCH_BIN环境变量或"which patch"找到补丁工具')

    if not patch_bin_path.exists():
        raise PatchNotFoundError(f'找不到补丁工具: {patch_bin_path}')

    # 确保patch能够实际运行
    cmd = [str(patch_bin_path), '--version']
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True,
            timeout=30  # 添加超时保护
        )
    except subprocess.TimeoutExpired as e:
        raise PatchExecutionError(f'补丁工具执行超时: {e}') from e
    except Exception as e:
        raise PatchExecutionError(f'执行补丁工具时出错: {e}') from e
        
    if result.returncode:
        logger = get_logger()
        logger.error(f'命令"{" ".join(cmd)}"返回非零退出码')
        logger.error(f'stdout:\n{result.stdout}')
        logger.error(f'stderr:\n{result.stderr}')
        raise PatchExecutionError(f'执行"{" ".join(cmd)}"时获得非零退出码')

    return patch_bin_path


def dry_run_check(patch_path: Path, tree_path: Path, 
                 patch_bin_path: Optional[Path] = None) -> Tuple[int, str, str]:
    """
    对补丁运行patch --dry-run
    
    Args:
        patch_path: 要检查的补丁文件路径
        tree_path: 要打补丁的源码树路径
        patch_bin_path: 补丁工具的路径，为None时自动查找
        
    Returns:
        (状态码, stdout, stderr)的元组
        
    Raises:
        PatchNotFoundError: 找不到补丁工具时
        PatchExecutionError: 补丁工具执行失败时
    """
    patch_tool = find_and_check_patch(patch_bin_path)
    
    cmd = [
        str(patch_tool), '-p1', '--ignore-whitespace', '-i',
        str(patch_path), '-d', str(tree_path), 
        '--no-backup-if-mismatch', '--dry-run'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True,
            timeout=300  # 5分钟超时
        )
        return result.returncode, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired as e:
        raise PatchExecutionError(f'补丁干运行超时: {e}') from e
    except Exception as e:
        raise PatchExecutionError(f'执行补丁干运行时出错: {e}') from e


def apply_patches(patch_path_iter: Iterator[Path], tree_path: Path, 
                 reverse: bool = False, patch_bin_path: Optional[Path] = None) -> None:
    """
    应用或撤销补丁列表
    
    Args:
        patch_path_iter: 要应用的补丁文件路径列表或元组
        tree_path: 要打补丁的源码树路径
        reverse: 是否撤销补丁
        patch_bin_path: 补丁工具的路径，为None时自动查找
        
    Raises:
        PatchNotFoundError: 找不到补丁工具时
        PatchExecutionError: 补丁应用失败时
    """
    patch_paths = list(patch_path_iter)
    patch_bin_path = find_and_check_patch(patch_bin_path=patch_bin_path)
    
    if reverse:
        patch_paths.reverse()

    logger = get_logger()
    total_patches = len(patch_paths)
    
    for patch_num, patch_path in enumerate(patch_paths, 1):
        cmd = [
            str(patch_bin_path), '-p1', '--ignore-whitespace', '-i',
            str(patch_path), '-d', str(tree_path), '--no-backup-if-mismatch'
        ]
        
        if reverse:
            cmd.append('--reverse')
            log_word = '撤销'
        else:
            cmd.append('--forward')
            log_word = '应用'
            
        logger.info(f'* {log_word} {patch_path.name} ({patch_num}/{total_patches})')
        logger.debug(f'执行命令: {" ".join(cmd)}')
        
        try:
            result = subprocess.run(
                cmd, 
                check=False,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f'补丁应用失败: {patch_path.name}')
                logger.error(f'stdout: {result.stdout}')
                logger.error(f'stderr: {result.stderr}')
                raise PatchExecutionError(f'应用补丁{patch_path.name}失败，退出码: {result.returncode}')
                
        except subprocess.TimeoutExpired as e:
            raise PatchExecutionError(f'应用补丁{patch_path.name}超时: {e}') from e
        except Exception as e:
            raise PatchExecutionError(f'应用补丁{patch_path.name}时出错: {e}') from e


def generate_patches_from_series(patches_dir: Path, resolve: bool = False) -> Iterator[Path]:
    """从GNU Quilt格式目录生成补丁的pathlib.Path
    
    Args:
        patches_dir: 补丁目录路径
        resolve: 是否解析为绝对路径
        
    Yields:
        补丁文件路径
    """
    series_file = patches_dir / 'series'
    if not series_file.exists():
        get_logger().warning(f'系列文件不存在: {series_file}')
        return
        
    for patch_path_str in parse_series(series_file):
        patch_path = Path(patch_path_str)
        if resolve:
            yield (patches_dir / patch_path).resolve()
        else:
            yield patch_path


def _copy_files(path_iter: Iterator[Path], source: Path, destination: Path) -> None:
    """从source复制文件到destination，使用path_iter中的相对路径
    
    Args:
        path_iter: 相对路径迭代器
        source: 源目录
        destination: 目标目录
    """
    for path in path_iter:
        dest_path = destination / path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        source_path = source / path
        if source_path.exists():
            shutil.copy2(str(source_path), str(dest_path))
        else:
            get_logger().warning(f'源文件不存在，跳过: {source_path}')


def merge_patches(source_iter: Iterator[Path], destination: Path, 
                 prepend: bool = False) -> None:
    """
    将GNU quilt格式的补丁目录从源合并到目标
    
    Args:
        source_iter: 源补丁目录迭代器
        destination: 目标目录
        prepend: 如果为True，源补丁将被添加到目标前面
        
    Raises:
        FileExistsError: 目标已存在且prepend为False，或补丁路径冲突时
        FileNotFoundError: prepend为True但目标中找不到series文件时
    """
    series = []
    known_paths = set()
    
    if destination.exists():
        if prepend:
            series_file = destination / 'series'
            if not series_file.exists():
                raise FileNotFoundError(f'在现有目标中找不到系列文件: {series_file}')
            known_paths.update(generate_patches_from_series(destination))
        else:
            raise FileExistsError(f'目标已存在: {destination}')
            
    for source_dir in source_iter:
        patch_paths = tuple(generate_patches_from_series(source_dir))
        patch_intersection = known_paths.intersection(patch_paths)
        
        if patch_intersection:
            raise FileExistsError(
                f'来自{source_dir}的补丁与其他源有冲突路径: {patch_intersection}'
            )
            
        series.extend(patch_paths)
        _copy_files(iter(patch_paths), source_dir, destination)
        known_paths.update(patch_paths)
        
    if prepend and (destination / 'series').exists():
        existing_patches = list(generate_patches_from_series(destination))
        series.extend(existing_patches)
        
    # 写入系列文件
    series_file = destination / 'series'
    with series_file.open('w', encoding='utf-8') as f:
        f.write('\n'.join(map(str, series)))


def _apply_callback(args: argparse.Namespace, parser_error) -> None:
    """应用补丁的命令行回调函数"""
    logger = get_logger()
    patch_bin_path = None
    
    if hasattr(args, 'patch_bin') and args.patch_bin is not None:
        patch_bin_path = Path(args.patch_bin)
        if not patch_bin_path.exists():
            patch_which = shutil.which(args.patch_bin)
            if patch_which:
                patch_bin_path = Path(patch_which)
            else:
                parser_error(f'指定的补丁工具不存在: {args.patch_bin}')
                
    try:
        patches_dir = Path(args.patches_dir)
        tree_path = Path(args.tree_path)
        
        if not patches_dir.exists():
            parser_error(f'补丁目录不存在: {patches_dir}')
        if not tree_path.exists():
            parser_error(f'源码树不存在: {tree_path}')
            
        patch_paths = generate_patches_from_series(patches_dir, resolve=True)
        apply_patches(patch_paths, tree_path, 
                     reverse=getattr(args, 'reverse', False),
                     patch_bin_path=patch_bin_path)
        
        logger.info('补丁应用完成')
        
    except (PatchError, FileNotFoundError, ValueError) as e:
        logger.error(f'补丁应用失败: {e}')
        parser_error(str(e))


def _merge_callback(args: argparse.Namespace, parser_error) -> None:
    """合并补丁的命令行回调函数"""
    try:
        source_dirs = [Path(d) for d in args.source_dirs]
        destination = Path(args.destination)
        
        for source_dir in source_dirs:
            if not source_dir.exists():
                parser_error(f'源目录不存在: {source_dir}')
                
        merge_patches(iter(source_dirs), destination, 
                     prepend=getattr(args, 'prepend', False))
        
        get_logger().info(f'补丁合并完成: {destination}')
        
    except (FileExistsError, FileNotFoundError, ValueError) as e:
        get_logger().error(f'补丁合并失败: {e}')
        parser_error(str(e))


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='补丁管理工具')
    add_common_params(parser)
    
    subparsers = parser.add_subparsers(dest='action', help='可用的操作')
    
    # 应用补丁子命令
    apply_parser = subparsers.add_parser('apply', help='应用补丁')
    apply_parser.add_argument('patches_dir', help='包含补丁的目录路径')
    apply_parser.add_argument('tree_path', help='要应用补丁的源码树路径')
    apply_parser.add_argument('--patch-bin', help='指定补丁工具的路径')
    apply_parser.add_argument('--reverse', action='store_true', help='撤销补丁')
    
    # 合并补丁子命令
    merge_parser = subparsers.add_parser('merge', help='合并补丁目录')
    merge_parser.add_argument('source_dirs', nargs='+', help='源补丁目录路径')
    merge_parser.add_argument('destination', help='目标目录路径')
    merge_parser.add_argument('--prepend', action='store_true', 
                             help='将源补丁添加到目标前面')
    
    args = parser.parse_args()
    
    def parser_error(msg: str):
        parser.error(msg)
    
    if args.action == 'apply':
        _apply_callback(args, parser_error)
    elif args.action == 'merge':
        _merge_callback(args, parser_error)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
