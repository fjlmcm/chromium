#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (c) 2020 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Applies unified diff patches"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from _common import get_logger, parse_series, add_common_params

# Constants
PATCH_ENV_VAR = 'PATCH_BIN'
PATCH_COMMAND = 'patch'

# Patch command arguments
PATCH_BASE_ARGS = ['-p1', '--ignore-whitespace', '--no-backup-if-mismatch']
PATCH_DRY_RUN_ARGS = PATCH_BASE_ARGS + ['--dry-run']
PATCH_FORWARD_ARGS = PATCH_BASE_ARGS + ['--forward']
PATCH_REVERSE_ARGS = PATCH_BASE_ARGS + ['--reverse']


class PatchError(Exception):
    """Exception for patch-related errors"""
    pass


class PatchNotFoundError(PatchError):
    """Exception for when patch binary cannot be found"""
    pass


def _find_patch_from_env():
    """
    Find patch binary from PATCH_BIN environment variable
    
    Returns:
        pathlib.Path to patch binary or None if not found/valid
    """
    patch_bin_env = os.environ.get(PATCH_ENV_VAR)
    if not patch_bin_env:
        get_logger().debug('%s env variable is not set', PATCH_ENV_VAR)
        return None
    
    patch_bin_path = Path(patch_bin_env)
    if patch_bin_path.exists():
        get_logger().debug('Found %s with path "%s"', PATCH_ENV_VAR, patch_bin_path)
        return patch_bin_path
    
    # Try to find it in PATH
    patch_which = shutil.which(patch_bin_env)
    if patch_which:
        get_logger().debug('Found %s for command with path "%s"', PATCH_ENV_VAR, patch_which)
        return Path(patch_which)
    
    get_logger().debug('%s env variable set but patch not found: %s', PATCH_ENV_VAR, patch_bin_env)
    return None


def _find_patch_from_which():
    """
    Find patch binary using 'which' command
    
    Returns:
        pathlib.Path to patch binary or None if not found
    """
    patch_which = shutil.which(PATCH_COMMAND)
    if not patch_which:
        get_logger().debug('Did not find "%s" in PATH environment variable', PATCH_COMMAND)
        return None
    return Path(patch_which)


def find_and_check_patch(patch_bin_path=None):
    """
    Find and verify the patch binary is working.
    
    Search order:
    1. Use patch_bin_path if provided
    2. Check PATCH_BIN environment variable
    3. Use 'which patch' to find GNU patch

    Args:
        patch_bin_path: Optional path to patch binary to use directly

    Returns:
        pathlib.Path to the verified patch binary

    Raises:
        PatchNotFoundError: If patch binary cannot be found
        PatchError: If patch binary fails verification
    """
    if patch_bin_path is None:
        patch_bin_path = _find_patch_from_env()
    if patch_bin_path is None:
        patch_bin_path = _find_patch_from_which()
    
    if not patch_bin_path:
        raise PatchNotFoundError(
            f'Could not find patch from {PATCH_ENV_VAR} env var or "which {PATCH_COMMAND}"'
        )

    if not patch_bin_path.exists():
        raise PatchNotFoundError(f'Could not find the patch binary: {patch_bin_path}')

    _verify_patch_binary(patch_bin_path)
    return patch_bin_path


def _verify_patch_binary(patch_bin_path):
    """
    Verify that patch binary works by running --version
    
    Args:
        patch_bin_path: Path to patch binary to verify
        
    Raises:
        PatchError: If patch binary fails verification
    """
    cmd = [str(patch_bin_path), '--version']
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PatchError(f'Failed to run patch binary verification: {exc}') from exc

    if result.returncode != 0:
        logger = get_logger()
        logger.error('"%s" returned non-zero exit code', ' '.join(cmd))
        logger.error('stdout:\n%s', result.stdout)
        logger.error('stderr:\n%s', result.stderr)
        raise PatchError(f'Patch binary verification failed with exit code {result.returncode}')


def dry_run_check(patch_path, tree_path, patch_bin_path=None):
    """
    Run patch --dry-run on a patch to check if it can be applied
    
    Args:
        patch_path: pathlib.Path to the patch file to check
        tree_path: pathlib.Path to the source tree to patch
        patch_bin_path: Optional path to patch binary (auto-detected if None)

    Returns:
        Tuple of (return_code, stdout, stderr) from patch --dry-run command
        
    Raises:
        PatchNotFoundError: If patch binary cannot be found
        PatchError: If patch binary verification fails
    """
    patch_binary = find_and_check_patch(patch_bin_path)
    
    cmd = [str(patch_binary)] + PATCH_DRY_RUN_ARGS + [
        '-i', str(patch_path),
        '-d', str(tree_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            universal_newlines=True
        )
        return result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        raise PatchError(f'Failed to run patch dry run: {exc}') from exc


def apply_patches(patch_path_iter, tree_path, reverse=False, patch_bin_path=None):
    """
    Apply or reverse a list of patches to a source tree

    Args:
        patch_path_iter: Iterable of pathlib.Path objects to patch files
        tree_path: pathlib.Path to the source tree to patch
        reverse: Whether to reverse the patches instead of applying them
        patch_bin_path: Optional path to patch binary (auto-detected if None)

    Raises:
        PatchNotFoundError: If patch binary cannot be found
        PatchError: If patch binary verification fails
        subprocess.CalledProcessError: If any patch application fails
    """
    patch_paths = list(patch_path_iter)
    patch_binary = find_and_check_patch(patch_bin_path)
    
    if reverse:
        patch_paths.reverse()

    _apply_patch_list(patch_binary, patch_paths, tree_path, reverse)


def _apply_patch_list(patch_binary, patch_paths, tree_path, reverse):
    """
    Apply a list of patches using the specified patch binary
    
    Args:
        patch_binary: Path to patch binary
        patch_paths: List of patch file paths
        tree_path: Path to source tree
        reverse: Whether to reverse patches
        
    Raises:
        subprocess.CalledProcessError: If any patch fails to apply
    """
    logger = get_logger()
    action_word = 'Reversing' if reverse else 'Applying'
    patch_args = PATCH_REVERSE_ARGS if reverse else PATCH_FORWARD_ARGS
    
    for patch_num, patch_path in enumerate(patch_paths, 1):
        cmd = [str(patch_binary)] + patch_args + [
            '-i', str(patch_path),
            '-d', str(tree_path)
        ]
        
        logger.info('* %s %s (%s/%s)', action_word, patch_path.name, patch_num, len(patch_paths))
        logger.debug(' '.join(cmd))
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise PatchError(
                f'Failed to {action_word.lower()} patch {patch_path.name}: {exc}'
            ) from exc


def generate_patches_from_series(patches_dir, resolve=False):
    """
    Generate pathlib.Path objects for patches from a directory in GNU Quilt format
    
    Args:
        patches_dir: Path to directory containing patches and series file
        resolve: Whether to resolve paths to absolute paths
        
    Yields:
        pathlib.Path objects for each patch in the series
        
    Raises:
        FileNotFoundError: If series file does not exist
        IOError: If series file cannot be read
    """
    for patch_path in parse_series(patches_dir / 'series'):
        if resolve:
            yield (patches_dir / patch_path).resolve()
        else:
            yield patch_path


def _copy_files(path_iter, source, destination):
    """
    Copy files from source to destination with relative paths from path_iter
    
    Args:
        path_iter: Iterable of relative paths to copy
        source: Source directory path
        destination: Destination directory path
    """
    for path in path_iter:
        dest_path = destination / path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source / path), str(dest_path))


def merge_patches(source_iter, destination, prepend=False):
    """
    Merge GNU quilt-formatted patch directories from sources into destination

    Args:
        source_iter: Iterable of source patch directories
        destination: Destination directory for merged patches
        prepend: If True, prepend source patches to existing destination patches

    Raises:
        FileExistsError: If destination exists and prepend is False, or if patches conflict
        FileNotFoundError: If series file is missing when prepend is True
    """
    series = []
    known_paths = set()
    
    if destination.exists():
        if prepend:
            series_file = destination / 'series'
            if not series_file.exists():
                raise FileNotFoundError(f'Could not find series file: {series_file}')
            known_paths.update(generate_patches_from_series(destination))
        else:
            raise FileExistsError(f'Destination already exists: {destination}')

    _merge_patch_sources(source_iter, destination, series, known_paths)
    
    if prepend and (destination / 'series').exists():
        series.extend(generate_patches_from_series(destination))
    
    _write_series_file(destination / 'series', series)


def _merge_patch_sources(source_iter, destination, series, known_paths):
    """
    Merge patches from multiple source directories
    
    Args:
        source_iter: Iterable of source directories
        destination: Destination directory
        series: List to append patch paths to
        known_paths: Set of known patch paths to check for conflicts
        
    Raises:
        FileExistsError: If patches conflict between sources
    """
    for source_dir in source_iter:
        patch_paths = tuple(generate_patches_from_series(source_dir))
        patch_intersection = known_paths.intersection(patch_paths)
        
        if patch_intersection:
            raise FileExistsError(
                f'Patches from {source_dir} have conflicting paths with other sources: '
                f'{patch_intersection}'
            )
        
        series.extend(patch_paths)
        known_paths.update(patch_paths)
        _copy_files(patch_paths, source_dir, destination)


def _write_series_file(series_path, series):
    """
    Write series file with patch paths
    
    Args:
        series_path: Path to series file to write
        series: List of patch paths to write
    """
    with series_path.open('w', encoding='utf-8') as series_file:
        series_file.write('\n'.join(map(str, series)))


def _apply_callback(args, parser_error):
    logger = get_logger()
    patch_bin_path = None
    if args.patch_bin is not None:
        patch_bin_path = Path(args.patch_bin)
        if not patch_bin_path.exists():
            patch_bin_path = shutil.which(args.patch_bin)
            if patch_bin_path:
                patch_bin_path = Path(patch_bin_path)
            else:
                parser_error(
                    f'--patch-bin "{args.patch_bin}" is not a command or path to executable.')
    for patch_dir in args.patches:
        logger.info('Applying patches from %s', patch_dir)
        apply_patches(generate_patches_from_series(patch_dir, resolve=True),
                      args.target,
                      patch_bin_path=patch_bin_path)


def _merge_callback(args, _):
    merge_patches(args.source, args.destination, args.prepend)


def main():
    """CLI Entrypoint"""
    parser = argparse.ArgumentParser()
    add_common_params(parser)
    subparsers = parser.add_subparsers()

    apply_parser = subparsers.add_parser(
        'apply', help='Applies patches (in GNU Quilt format) to the specified source tree')
    apply_parser.add_argument('--patch-bin',
                              help='The GNU patch command to use. Omit to find it automatically.')
    apply_parser.add_argument('target', type=Path, help='The directory tree to apply patches onto.')
    apply_parser.add_argument(
        'patches',
        type=Path,
        nargs='+',
        help='The directories containing patches to apply. They must be in GNU quilt format')
    apply_parser.set_defaults(callback=_apply_callback)

    merge_parser = subparsers.add_parser('merge',
                                         help='Merges patches directories in GNU quilt format')
    merge_parser.add_argument(
        '--prepend',
        '-p',
        action='store_true',
        help=('If "destination" exists, prepend patches from sources into it.'
              ' By default, merging will fail if the destination already exists.'))
    merge_parser.add_argument(
        'destination',
        type=Path,
        help=('The directory to write the merged patches to. '
              'The destination must not exist unless --prepend is specified.'))
    merge_parser.add_argument('source',
                              type=Path,
                              nargs='+',
                              help='The GNU quilt patches to merge.')
    merge_parser.set_defaults(callback=_merge_callback)

    args = parser.parse_args()
    if 'callback' not in args:
        parser.error('Must specify subcommand apply or merge')
    args.callback(args, parser.error)


if __name__ == '__main__':
    main()
