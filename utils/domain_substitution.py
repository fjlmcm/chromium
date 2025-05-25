#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (c) 2019 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Substitute domain names in the source tree with blockable strings.
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

from _extraction import extract_tar_file
from _common import ENCODING, get_logger, add_common_params

# Constants

# Encodings to try on source tree files
TREE_ENCODINGS = ('UTF-8', 'ISO-8859-1')

# Domain substitution cache file constants
INDEX_LIST_FILENAME = 'cache_index.list'
INDEX_HASH_DELIMITER = '|'
ORIG_DIR_NAME = 'orig'

# Timestamp manipulation constants
TIMESTAMP_DELTA = 1 * 10**9  # Delta between all file timestamps in nanoseconds

# Domain regex pattern constants
PATTERN_REPLACE_DELIMITER = '#'

# Validation constants
CRC32_REGEX_PATTERN = r'^[a-zA-Z0-9]{8}$'


class DomainSubstitutionError(Exception):
    """Base exception for domain substitution errors"""
    pass


class DomainRegexError(DomainSubstitutionError):
    """Exception for domain regex compilation or processing errors"""
    pass


class FileProcessingError(DomainSubstitutionError):
    """Exception for file processing errors during domain substitution"""
    pass


class DomainRegexList:
    """Representation of a domain_regex.list file"""
    
    _regex_pair_tuple = collections.namedtuple('DomainRegexPair', ('pattern', 'replacement'))

    def __init__(self, path):
        """
        Initialize domain regex list from file
        
        Args:
            path: pathlib.Path to domain_regex.list file
            
        Raises:
            FileNotFoundError: If the file does not exist
            IOError: If the file cannot be read
        """
        try:
            self._data = tuple(filter(len, path.read_text(encoding=ENCODING).splitlines()))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Domain regex file not found: {path}") from exc
        except IOError as exc:
            raise IOError(f"Cannot read domain regex file: {path}") from exc

        # Cache of compiled regex pairs
        self._compiled_regex = None

    def _compile_regex(self, line):
        """
        Generate a regex pair tuple for the given line
        
        Args:
            line: Line from domain regex file
            
        Returns:
            Compiled regex pair tuple
            
        Raises:
            DomainRegexError: If line format is invalid or regex compilation fails
        """
        try:
            pattern, replacement = line.split(PATTERN_REPLACE_DELIMITER, 1)
        except ValueError as exc:
            raise DomainRegexError(f"Invalid regex line format: {line}") from exc
        
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as exc:
            raise DomainRegexError(f"Failed to compile regex pattern '{pattern}': {exc}") from exc
        
        return self._regex_pair_tuple(compiled_pattern, replacement)

    @property
    def regex_pairs(self):
        """
        Returns a tuple of compiled regex pairs
        
        Returns:
            Tuple of DomainRegexPair namedtuples with compiled patterns
        """
        if not self._compiled_regex:
            self._compiled_regex = tuple(map(self._compile_regex, self._data))
        return self._compiled_regex

    @property
    def search_regex(self):
        """
        Returns a single expression to search for domains
        
        Returns:
            Compiled regex pattern for searching all domain patterns
        """
        pattern_strings = [
            line.split(PATTERN_REPLACE_DELIMITER, 1)[0] for line in self._data
        ]
        combined_pattern = '|'.join(pattern_strings)
        return re.compile(combined_pattern)


def _substitute_path(path, regex_iter):
    """
    Perform domain substitution on path and return substitution info.

    Args:
        path: pathlib.Path to the file to be domain substituted
        regex_iter: Iterable of regex pairs for substitution

    Returns:
        Tuple of (CRC32 hash of substituted content, original content bytes);
        (None, None) if no substitutions were made

    Raises:
        FileNotFoundError: If path does not exist
        UnicodeDecodeError: If path's contents cannot be decoded
        FileProcessingError: If file cannot be processed
    """
    if not path.exists():
        raise FileNotFoundError(f"File to substitute not found: {path}")
    
    # Ensure file is writable
    if not os.access(path, os.W_OK):
        get_logger().debug("Adding write permission to %s", path)
        path.chmod(path.stat().st_mode | stat.S_IWUSR)

    try:
        with path.open('r+b') as input_file:
            original_content = input_file.read()
            if not original_content:
                return (None, None)

            # Try to decode with supported encodings
            content = _decode_file_content(original_content, path)
            
            # Apply substitutions
            substituted_content, total_subs = _apply_regex_substitutions(content, regex_iter)
            
            if total_subs > 0:
                encoded_content = substituted_content.encode(TREE_ENCODINGS[0])  # Use UTF-8 for output
                input_file.seek(0)
                input_file.write(encoded_content)
                input_file.truncate()
                return (zlib.crc32(encoded_content), original_content)
            
            return (None, None)
    except (OSError, IOError) as exc:
        raise FileProcessingError(f"Cannot process file {path}: {exc}") from exc


def _decode_file_content(content_bytes, file_path):
    """
    Decode file content using supported encodings
    
    Args:
        content_bytes: Raw file content as bytes
        file_path: Path to file for error reporting
        
    Returns:
        Decoded string content
        
    Raises:
        UnicodeDecodeError: If content cannot be decoded with any supported encoding
    """
    for encoding in TREE_ENCODINGS:
        try:
            return content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    raise UnicodeDecodeError(f'Unable to decode file with any supported encoding: {file_path}')


def _apply_regex_substitutions(content, regex_iter):
    """
    Apply regex substitutions to content
    
    Args:
        content: String content to process
        regex_iter: Iterable of regex pairs for substitution
        
    Returns:
        Tuple of (substituted_content, total_substitution_count)
    """
    total_subs = 0
    for regex_pair in regex_iter:
        content, sub_count = regex_pair.pattern.subn(regex_pair.replacement, content)
        total_subs += sub_count
    
    return content, total_subs


def _validate_file_index(index_file, resolved_tree, cache_index_files):
    """
    Validate file index and hashes against the source tree
    
    Args:
        index_file: Open file object for the index file
        resolved_tree: Resolved path to source tree
        cache_index_files: Set to update with processed file paths
        
    Returns:
        Boolean indicating if the file index is valid
    """
    all_hashes_valid = True
    crc32_regex = re.compile(CRC32_REGEX_PATTERN)
    
    try:
        index_content = index_file.read().decode(ENCODING)
    except (IOError, UnicodeDecodeError) as exc:
        get_logger().error('Cannot read or decode index file: %s', exc)
        return False
    
    for entry in index_content.splitlines():
        if not _validate_index_entry(entry, resolved_tree, cache_index_files, crc32_regex):
            all_hashes_valid = False
    
    return all_hashes_valid


def _validate_index_entry(entry, resolved_tree, cache_index_files, crc32_regex):
    """
    Validate a single index entry
    
    Args:
        entry: Index entry string to validate
        resolved_tree: Resolved path to source tree
        cache_index_files: Set of processed file paths
        crc32_regex: Compiled regex for CRC32 validation
        
    Returns:
        Boolean indicating if entry is valid
    """
    try:
        relative_path, file_hash = entry.split(INDEX_HASH_DELIMITER, 1)
    except ValueError as exc:
        get_logger().error('Could not split entry "%s": %s', entry, exc)
        return False

    if not relative_path or not file_hash:
        get_logger().error('Invalid index entry: %s', entry)
        return False

    if not crc32_regex.match(file_hash):
        get_logger().error('File hash for %s does not appear to be a CRC32 hash', relative_path)
        return False

    file_path = resolved_tree / relative_path
    if not file_path.exists():
        get_logger().error('File does not exist: %s', relative_path)
        return False

    try:
        actual_hash = zlib.crc32(file_path.read_bytes())
        if actual_hash != int(file_hash, 16):
            get_logger().error('Hash mismatch for: %s', relative_path)
            return False
    except (IOError, ValueError) as exc:
        get_logger().error('Cannot verify hash for %s: %s', relative_path, exc)
        return False

    if relative_path in cache_index_files:
        get_logger().error('File %s appears multiple times in the index', relative_path)
        return False

    cache_index_files.add(relative_path)
    return True


@contextlib.contextmanager
def _update_timestamp(path, set_new):
    """
    Context manager to adjust file timestamp by a fixed delta
    
    Args:
        path: Path to file to modify timestamp
        set_new: If True, add delta; if False, subtract delta
        
    Yields:
        None (context manager)
    """
    try:
        stats = os.stat(path)
    except OSError as exc:
        get_logger().warning('Cannot get stats for %s: %s', path, exc)
        yield
        return
    
    if set_new:
        new_timestamp = (
            stats.st_atime_ns + TIMESTAMP_DELTA,
            stats.st_mtime_ns + TIMESTAMP_DELTA
        )
    else:
        new_timestamp = (
            stats.st_atime_ns - TIMESTAMP_DELTA,
            stats.st_mtime_ns - TIMESTAMP_DELTA
        )
    
    try:
        yield
    finally:
        try:
            os.utime(path, ns=new_timestamp)
        except OSError as exc:
            get_logger().warning('Cannot update timestamp for %s: %s', path, exc)


# Public Methods


def apply_substitution(regex_path, files_path, source_tree, domainsub_cache):
    """
    Substitute domains in source_tree with files and substitutions,
        and save the pre-domain substitution archive to presubdom_archive.

    regex_path is a pathlib.Path to domain_regex.list
    files_path is a pathlib.Path to domain_substitution.list
    source_tree is a pathlib.Path to the source tree.
    domainsub_cache is a pathlib.Path to the domain substitution cache.

    Raises NotADirectoryError if the patches directory is not a directory or does not exist
    Raises FileNotFoundError if the source tree or required directory does not exist.
    Raises FileExistsError if the domain substitution cache already exists.
    Raises ValueError if an entry in the domain substitution list contains the file index
        hash delimiter.
    """
    if not source_tree.exists():
        raise FileNotFoundError(source_tree)
    if not regex_path.exists():
        raise FileNotFoundError(regex_path)
    if not files_path.exists():
        raise FileNotFoundError(files_path)
    if domainsub_cache and domainsub_cache.exists():
        raise FileExistsError(domainsub_cache)
    resolved_tree = source_tree.resolve()
    regex_pairs = DomainRegexList(regex_path).regex_pairs
    fileindex_content = io.BytesIO()
    with tarfile.open(str(domainsub_cache), 'w:%s' % domainsub_cache.suffix[1:],
                      compresslevel=1) if domainsub_cache else open(os.devnull, 'w') as cache_tar:
        for relative_path in filter(len, files_path.read_text().splitlines()):
            if _INDEX_HASH_DELIMITER in relative_path:
                if domainsub_cache:
                    # Cache tar will be incomplete; remove it for convenience
                    cache_tar.close()
                    domainsub_cache.unlink()
                raise ValueError(
                    'Path "%s" contains the file index hash delimiter "%s"' % relative_path,
                    _INDEX_HASH_DELIMITER)
            path = resolved_tree / relative_path
            if not path.exists():
                get_logger().warning('Skipping non-existant path: %s', path)
                continue
            if path.is_symlink():
                get_logger().warning('Skipping path that has become a symlink: %s', path)
                continue
            with _update_timestamp(path, set_new=True):
                crc32_hash, orig_content = _substitute_path(path, regex_pairs)
            if crc32_hash is None:
                get_logger().info('Path has no substitutions: %s', relative_path)
                continue
            if domainsub_cache:
                fileindex_content.write('{}{}{:08x}\n'.format(relative_path, _INDEX_HASH_DELIMITER,
                                                              crc32_hash).encode(ENCODING))
                orig_tarinfo = tarfile.TarInfo(str(Path(_ORIG_DIR) / relative_path))
                orig_tarinfo.size = len(orig_content)
                with io.BytesIO(orig_content) as orig_file:
                    cache_tar.addfile(orig_tarinfo, orig_file)
        if domainsub_cache:
            fileindex_tarinfo = tarfile.TarInfo(_INDEX_LIST)
            fileindex_tarinfo.size = fileindex_content.tell()
            fileindex_content.seek(0)
            cache_tar.addfile(fileindex_tarinfo, fileindex_content)


def revert_substitution(domainsub_cache, source_tree):
    """
    Revert domain substitution on source_tree using the pre-domain
        substitution archive presubdom_archive.
    It first checks if the hashes of the substituted files match the hashes
        computed during the creation of the domain substitution cache, raising
        KeyError if there are any mismatches. Then, it proceeds to
        reverting files in the source_tree.
    domainsub_cache is removed only if all the files from the domain substitution cache
        were relocated to the source tree.

    domainsub_cache is a pathlib.Path to the domain substitution cache.
    source_tree is a pathlib.Path to the source tree.

    Raises KeyError if:
        * There is a hash mismatch while validating the cache
        * The cache's file index is corrupt or missing
        * The cache is corrupt or is not consistent with the file index
    Raises FileNotFoundError if the source tree or domain substitution cache do not exist.
    """
    # This implementation trades disk space/wear for performance (unless a ramdisk is used
    #   for the source tree)
    # Assumptions made for this process:
    # * The correct tar file was provided (so no huge amount of space is wasted)
    # * The tar file is well-behaved (e.g. no files extracted outside of destination path)
    # * Cache file index and cache contents are already consistent (i.e. no files exclusive to
    #   one or the other)
    if not domainsub_cache:
        get_logger().error('Cache file must be specified.')
    if not domainsub_cache.exists():
        raise FileNotFoundError(domainsub_cache)
    if not source_tree.exists():
        raise FileNotFoundError(source_tree)
    resolved_tree = source_tree.resolve()

    cache_index_files = set() # All files in the file index

    with tempfile.TemporaryDirectory(prefix='domsubcache_files',
                                     dir=str(resolved_tree)) as tmp_extract_name:
        extract_path = Path(tmp_extract_name)
        get_logger().debug('Extracting domain substitution cache...')
        extract_tar_file(domainsub_cache, extract_path, None)

        # Validate source tree file hashes match
        get_logger().debug('Validating substituted files in source tree...')
        with (extract_path / _INDEX_LIST).open('rb') as index_file: #pylint: disable=no-member
            if not _validate_file_index(index_file, resolved_tree, cache_index_files):
                raise KeyError('Domain substitution cache file index is corrupt or hashes mismatch '
                               'the source tree.')

        # Move original files over substituted ones
        get_logger().debug('Moving original files over substituted ones...')
        for relative_path in cache_index_files:
            with _update_timestamp(resolved_tree / relative_path, set_new=False):
                (extract_path / _ORIG_DIR / relative_path).replace(resolved_tree / relative_path)

        # Quick check for unused files in cache
        orig_has_unused = False
        for orig_path in (extract_path / _ORIG_DIR).rglob('*'): #pylint: disable=no-member
            if orig_path.is_file():
                get_logger().warning('Unused file from cache: %s', orig_path)
                orig_has_unused = True

    if orig_has_unused:
        get_logger().warning('Cache contains unused files. Not removing.')
    else:
        domainsub_cache.unlink()


def _callback(args):
    """CLI Callback"""
    if args.reverting:
        revert_substitution(args.cache, args.directory)
    else:
        apply_substitution(args.regex, args.files, args.directory, args.cache)


def main():
    """CLI Entrypoint"""
    parser = argparse.ArgumentParser()
    add_common_params(parser)
    parser.set_defaults(callback=_callback)
    subparsers = parser.add_subparsers(title='', dest='packaging')

    # apply
    apply_parser = subparsers.add_parser(
        'apply',
        help='Apply domain substitution',
        description='Applies domain substitution and creates the domain substitution cache.')
    apply_parser.add_argument('-r',
                              '--regex',
                              type=Path,
                              required=True,
                              help='Path to domain_regex.list')
    apply_parser.add_argument('-f',
                              '--files',
                              type=Path,
                              required=True,
                              help='Path to domain_substitution.list')
    apply_parser.add_argument(
        '-c',
        '--cache',
        type=Path,
        help='The path to the domain substitution cache. The path must not already exist.')
    apply_parser.add_argument('directory',
                              type=Path,
                              help='The directory to apply domain substitution')
    apply_parser.set_defaults(reverting=False)

    # revert
    revert_parser = subparsers.add_parser(
        'revert',
        help='Revert domain substitution',
        description='Reverts domain substitution based only on the domain substitution cache.')
    revert_parser.add_argument('directory',
                               type=Path,
                               help='The directory to reverse domain substitution')
    revert_parser.add_argument('-c',
                               '--cache',
                               type=Path,
                               required=True,
                               help=('The path to the domain substitution cache. '
                                     'The path must exist and will be removed if successful.'))
    revert_parser.set_defaults(reverting=True)

    args = parser.parse_args()
    args.callback(args)


if __name__ == '__main__':
    main()
