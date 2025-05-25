#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (c) 2019 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Module for the downloading, checking, and unpacking of necessary files into the source tree.
"""

import argparse
import configparser
import enum
import hashlib
import shutil
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

from _common import ENCODING, USE_REGISTRY, ExtractorEnum, PlatformEnum, \
    get_logger, get_chromium_version, get_running_platform, add_common_params
from _extraction import extract_tar_file, extract_with_7z, extract_with_winrar

sys.path.insert(0, str(Path(__file__).parent / 'third_party'))
import schema  # pylint: disable=wrong-import-position, wrong-import-order
sys.path.pop(0)

# Constants

# Hash verification constants
SUPPORTED_HASHES = ('md5', 'sha1', 'sha256', 'sha512')
HASH_URL_DELIMITER = '|'
DEFAULT_CHUNK_SIZE = 262144  # 256KB chunks for hash verification

# INI file keys
REQUIRED_KEYS = ('url', 'download_filename')
OPTIONAL_KEYS = ('version', 'strip_leading_dirs')

# Download progress constants
PROGRESS_UPDATE_THRESHOLD = 0.001  # Update progress only when it changes by 0.1%


class HashesURLEnum(str, enum.Enum):
    """Enum for supported hash URL schemes"""
    CHROMIUM = 'chromium'


class HashMismatchError(Exception):
    """Exception for computed hashes not matching expected hashes"""
    def __init__(self, file_path, expected_hash=None, actual_hash=None):
        self.file_path = file_path
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(f"Hash mismatch for {file_path}")


class DownloadInfo:  # pylint: disable=too-few-public-methods
    """Representation of a downloads.ini file for downloading files"""

    _passthrough_properties = (*REQUIRED_KEYS, *OPTIONAL_KEYS, 'extractor', 'output_path')
    _ini_vars = {
        '_chromium_version': get_chromium_version(),
    }

    @staticmethod
    def _is_hash_url(value):
        """Check if value is a valid hash URL format"""
        return (value.count(HASH_URL_DELIMITER) == 2 and 
                value.split(HASH_URL_DELIMITER)[0] in iter(HashesURLEnum))

    def _create_schema(self):
        """Create and return the validation schema for downloads.ini"""
        return schema.Schema({
            schema.Optional(schema.And(str, len)): {
                **{key: schema.And(str, len) for key in REQUIRED_KEYS},
                'output_path': (lambda x: str(Path(x).relative_to(''))),
                **{schema.Optional(key): schema.And(str, len) for key in OPTIONAL_KEYS},
                schema.Optional('extractor'): schema.Or(
                    ExtractorEnum.TAR, ExtractorEnum.SEVENZIP, ExtractorEnum.WINRAR
                ),
                **{schema.Optional(hash_type): schema.And(str, len) for hash_type in SUPPORTED_HASHES},
                schema.Optional('hash_url'): self._is_hash_url,
            }
        })

    class _DownloadsProperties:  # pylint: disable=too-few-public-methods
        """Properties accessor for download sections"""
        
        def __init__(self, section_dict, passthrough_properties):
            self._section_dict = section_dict
            self._passthrough_properties = passthrough_properties

        def has_hash_url(self):
            """Returns True if the current download has a hash URL"""
            return 'hash_url' in self._section_dict

        def _get_hashes_dict(self):
            """Get dictionary of all hashes for this download"""
            hashes_dict = {}
            for hash_name in (*SUPPORTED_HASHES, 'hash_url'):
                value = self._section_dict.get(hash_name, fallback=None)
                if value:
                    if hash_name == 'hash_url':
                        value = value.split(HASH_URL_DELIMITER)
                    hashes_dict[hash_name] = value
            return hashes_dict

        def __getattr__(self, name):
            if name in self._passthrough_properties:
                return self._section_dict.get(name, fallback=None)
            if name == 'hashes':
                return self._get_hashes_dict()
            raise AttributeError(f'"{type(self).__name__}" has no attribute "{name}"')

    def _parse_data(self, path):
        """
        Parse an INI file located at path
        
        Raises:
            schema.SchemaError: If validation fails
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
        """
        def _section_generator(data):
            """Generate sections excluding defaults and ini variables"""
            for section in data:
                if section == configparser.DEFAULTSECT:
                    continue
                yield section, dict(
                    filter(lambda x: x[0] not in self._ini_vars, data.items(section))
                )

        new_data = configparser.ConfigParser(defaults=self._ini_vars)
        try:
            with path.open(encoding=ENCODING) as ini_file:
                new_data.read_file(ini_file, source=str(path))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Downloads INI file not found: {path}") from exc
        except IOError as exc:
            raise IOError(f"Cannot read downloads INI file: {path}") from exc
        
        try:
            self._schema.validate(dict(_section_generator(new_data)))
        except schema.SchemaError as exc:
            get_logger().error('downloads.ini failed schema validation (located in %s)', path)
            raise exc
        
        return new_data

    def __init__(self, ini_paths):
        """
        Initialize DownloadInfo from iterable of pathlib.Path to download.ini files
        
        Args:
            ini_paths: Iterable of pathlib.Path objects pointing to downloads.ini files
        """
        self._schema = self._create_schema()
        self._data = configparser.ConfigParser()
        
        for path in ini_paths:
            self._data.read_dict(self._parse_data(path))

    def __getitem__(self, section):
        """
        Returns an object with keys as attributes and values already pre-processed strings
        
        Args:
            section: Section name to retrieve
            
        Returns:
            _DownloadsProperties object for the section
        """
        return self._DownloadsProperties(self._data[section], self._passthrough_properties)

    def __contains__(self, item):
        """
        Returns True if item is a name of a section; False otherwise
        
        Args:
            item: Section name to check
            
        Returns:
            Boolean indicating if section exists
        """
        return self._data.has_section(item)

    def __iter__(self):
        """Returns an iterator over the section names"""
        return iter(self._data.sections())

    def properties_iter(self):
        """Iterator for the download properties sorted by output path"""
        return sorted(
            map(lambda x: (x, self[x]), self),
            key=(lambda x: str(Path(x[1].output_path)))
        )

    def check_sections_exist(self, section_names):
        """
        Verify that all specified section names exist
        
        Args:
            section_names: Iterable of section names to check
            
        Raises:
            KeyError: If any section does not exist
        """
        if not section_names:
            return
            
        for name in section_names:
            if name not in self:
                raise KeyError(f'DownloadInfo has no section "{name}"')


class _UrlRetrieveReportHook:  # pylint: disable=too-few-public-methods
    """Hook for urllib.request.urlretrieve to log progress information to console"""
    
    def __init__(self):
        self._max_len_printed = 0
        self._last_percentage = None

    def __call__(self, block_count, block_size, total_size):
        """Report download progress"""
        # Use total_blocks to handle case total_size < block_size
        # total_blocks is ceiling of total_size / block_size
        # Ceiling division from: https://stackoverflow.com/a/17511341
        total_blocks = -(-total_size // block_size)
        
        if total_blocks > 0:
            # Only refresh output when the displayed value should change
            # to avoid bottlenecking the download with console updates
            percentage = round(block_count / total_blocks, ndigits=3)
            if percentage == self._last_percentage:
                return
            self._last_percentage = percentage
            
            print('\r' + ' ' * self._max_len_printed, end='')
            status_line = f'Progress: {percentage:.1%} of {total_size:,d} B'
        else:
            downloaded_estimate = block_count * block_size
            status_line = f'Progress: {downloaded_estimate:,d} B of unknown size'
        
        self._max_len_printed = len(status_line)
        print('\r' + status_line, end='')


def _download_via_urllib(url, file_path, show_progress, disable_ssl_verification):
    """
    Download file using urllib with optional progress reporting and SSL verification control
    
    Args:
        url: URL to download from
        file_path: Local path to save file to
        show_progress: Whether to show progress information
        disable_ssl_verification: Whether to disable SSL certificate verification
    """
    reporthook = None
    if show_progress:
        reporthook = _UrlRetrieveReportHook()
    
    orig_https_context = None
    if disable_ssl_verification:
        # TODO: Remove this or properly implement disabling SSL certificate verification
        orig_https_context = ssl._create_default_https_context  # pylint: disable=protected-access
        ssl._create_default_https_context = ssl._create_unverified_context  # pylint: disable=protected-access
    
    try:
        urllib.request.urlretrieve(url, str(file_path), reporthook=reporthook)
    finally:
        # Try to reduce damage of hack by reverting original HTTPS context ASAP
        if disable_ssl_verification and orig_https_context:
            ssl._create_default_https_context = orig_https_context  # pylint: disable=protected-access
    
    if show_progress:
        print()  # Add newline after progress output


def _download_if_needed(file_path, url, show_progress, disable_ssl_verification):
    """
    Download a file from url to the specified path if necessary.
    
    Args:
        file_path: pathlib.Path where to save the file
        url: URL to download from
        show_progress: Whether to show download progress
        disable_ssl_verification: Whether to disable SSL certificate verification
        
    Raises:
        subprocess.CalledProcessError: If curl download fails
        Various urllib exceptions: If urllib download fails
    """
    if file_path.exists():
        get_logger().info('%s already exists. Skipping download.', file_path)
        return

    # File name for partially downloaded file
    tmp_file_path = file_path.with_name(file_path.name + '.partial')

    if tmp_file_path.exists():
        get_logger().debug('Resuming downloading URL %s ...', url)
    else:
        get_logger().debug('Downloading URL %s ...', url)

    # Perform download - prefer curl if available for better resume support
    curl_path = shutil.which('curl')
    if curl_path:
        get_logger().debug('Using curl')
        _download_with_curl(url, tmp_file_path)
    else:
        get_logger().debug('Using urllib')
        _download_via_urllib(url, tmp_file_path, show_progress, disable_ssl_verification)

    # Download complete; rename file
    tmp_file_path.rename(file_path)


def _download_with_curl(url, file_path):
    """
    Download file using curl with resume support
    
    Args:
        url: URL to download from
        file_path: Local path to save file to
        
    Raises:
        subprocess.CalledProcessError: If curl command fails
    """
    try:
        subprocess.run([
            'curl', '-fL', '-o', str(file_path), '-C', '-', url
        ], check=True)
    except subprocess.CalledProcessError as exc:
        get_logger().error('curl failed. Re-run the download command to resume downloading.')
        raise exc


def _chromium_hashes_generator(hashes_path):
    """
    Parse Chromium-style hash file and yield (hash_name, hash_hex) pairs
    
    Args:
        hashes_path: Path to the hash file
        
    Yields:
        Tuple of (hash_name, hash_hex) for supported hash algorithms
        
    Raises:
        FileNotFoundError: If hash file does not exist
        IOError: If hash file cannot be read
    """
    try:
        with hashes_path.open(encoding=ENCODING) as hashes_file:
            hash_lines = hashes_file.read().splitlines()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Hash file not found: {hashes_path}") from exc
    except IOError as exc:
        raise IOError(f"Cannot read hash file: {hashes_path}") from exc
    
    for line in hash_lines:
        parts = line.lower().split('  ')
        if len(parts) >= 2:
            hash_name, hash_hex = parts[0], parts[1]
            if hash_name in hashlib.algorithms_available:
                yield hash_name, hash_hex
            else:
                get_logger().warning('Skipping unknown hash algorithm: %s', hash_name)


def _get_hash_pairs(download_properties, cache_dir):
    """
    Generator of (hash_name, hash_hex) pairs for the given download
    
    Args:
        download_properties: Download properties object
        cache_dir: Path to the downloads cache directory
        
    Yields:
        Tuple of (hash_name, hash_hex) for verification
        
    Raises:
        ValueError: If unknown hash_url processor is encountered
    """
    for entry_type, entry_value in download_properties.hashes.items():
        if entry_type == 'hash_url':
            hash_processor, hash_filename, _ = entry_value
            if hash_processor == HashesURLEnum.CHROMIUM:
                yield from _chromium_hashes_generator(cache_dir / hash_filename)
            else:
                raise ValueError(f'Unknown hash_url processor: {hash_processor}')
        else:
            yield entry_type, entry_value


def retrieve_downloads(download_info, cache_dir, components, show_progress, 
                       disable_ssl_verification=False):
    """
    Retrieve downloads into the downloads cache.

    Args:
        download_info: DownloadInfo instance containing download configurations
        cache_dir: pathlib.Path to the downloads cache directory
        components: List of component names to download (empty list means download all)
        show_progress: Whether to show download progress to console
        disable_ssl_verification: Whether to disable HTTPS certificate verification

    Raises:
        FileNotFoundError: If the downloads cache directory does not exist
        NotADirectoryError: If the downloads cache path is not a directory
        Various download exceptions: From underlying download mechanisms
    """
    _validate_cache_directory(cache_dir)
    
    for download_name, download_properties in download_info.properties_iter():
        if components and download_name not in components:
            continue
            
        _download_component(download_name, download_properties, cache_dir, 
                          show_progress, disable_ssl_verification)


def _validate_cache_directory(cache_dir):
    """
    Validate that cache directory exists and is a directory
    
    Args:
        cache_dir: Path to validate
        
    Raises:
        FileNotFoundError: If directory does not exist
        NotADirectoryError: If path is not a directory
    """
    if not cache_dir.exists():
        raise FileNotFoundError(f"Downloads cache directory not found: {cache_dir}")
    if not cache_dir.is_dir():
        raise NotADirectoryError(f"Downloads cache path is not a directory: {cache_dir}")


def _download_component(download_name, download_properties, cache_dir, 
                       show_progress, disable_ssl_verification):
    """
    Download a single component and its associated hash files
    
    Args:
        download_name: Name of the component being downloaded
        download_properties: Properties object for the download
        cache_dir: Path to downloads cache directory
        show_progress: Whether to show download progress
        disable_ssl_verification: Whether to disable SSL verification
    """
    get_logger().info('Downloading "%s" to "%s" ...', download_name,
                      download_properties.download_filename)
    
    download_path = cache_dir / download_properties.download_filename
    _download_if_needed(download_path, download_properties.url, show_progress,
                        disable_ssl_verification)
    
    if download_properties.has_hash_url():
        get_logger().info('Downloading hashes for "%s"', download_name)
        _, hash_filename, hash_url = download_properties.hashes['hash_url']
        _download_if_needed(cache_dir / hash_filename, hash_url, show_progress,
                            disable_ssl_verification)


def check_downloads(download_info, cache_dir, components, chunk_bytes=None):
    """
    Check integrity of the downloads cache using hash verification.

    Args:
        download_info: DownloadInfo instance containing download configurations
        cache_dir: pathlib.Path to the downloads cache directory
        components: List of component names to check (empty list means check all)
        chunk_bytes: Size of chunks for reading files (defaults to DEFAULT_CHUNK_SIZE)

    Raises:
        HashMismatchError: When computed and expected hashes do not match
        FileNotFoundError: If download file does not exist
        IOError: If file cannot be read
    """
    if chunk_bytes is None:
        chunk_bytes = DEFAULT_CHUNK_SIZE
        
    logger = get_logger()
    
    for download_name, download_properties in download_info.properties_iter():
        if components and download_name not in components:
            continue
            
        logger.info('Verifying hashes for "%s" ...', download_name)
        download_path = cache_dir / download_properties.download_filename
        
        _verify_download_hashes(download_path, download_properties, cache_dir, chunk_bytes)


def _verify_download_hashes(download_path, download_properties, cache_dir, chunk_bytes):
    """
    Verify all hashes for a single download
    
    Args:
        download_path: Path to the downloaded file
        download_properties: Properties object for the download
        cache_dir: Path to downloads cache directory
        chunk_bytes: Size of chunks for reading files
        
    Raises:
        HashMismatchError: If any hash verification fails
        FileNotFoundError: If download file does not exist
    """
    logger = get_logger()
    
    if not download_path.exists():
        raise FileNotFoundError(f"Download file not found: {download_path}")
    
    for hash_name, expected_hash in _get_hash_pairs(download_properties, cache_dir):
        logger.info('Verifying %s hash...', hash_name)
        actual_hash = _compute_file_hash(download_path, hash_name, chunk_bytes)
        
        if actual_hash.lower() != expected_hash.lower():
            raise HashMismatchError(download_path, expected_hash, actual_hash)


def _compute_file_hash(file_path, hash_name, chunk_bytes):
    """
    Compute hash of a file using specified algorithm
    
    Args:
        file_path: Path to file to hash
        hash_name: Name of hash algorithm to use
        chunk_bytes: Size of chunks for reading file
        
    Returns:
        Hexadecimal string of the computed hash
        
    Raises:
        IOError: If file cannot be read
        ValueError: If hash algorithm is not supported
    """
    try:
        hasher = hashlib.new(hash_name)
    except ValueError as exc:
        raise ValueError(f"Unsupported hash algorithm: {hash_name}") from exc
    
    try:
        with file_path.open('rb') as file_obj:
            while True:
                chunk = file_obj.read(chunk_bytes)
                if not chunk:
                    break
                hasher.update(chunk)
    except IOError as exc:
        raise IOError(f"Cannot read file for hashing: {file_path}") from exc
    
    return hasher.hexdigest()


def unpack_downloads(download_info, cache_dir, components, output_dir, extractors=None):
    """
    Unpack downloads in the downloads cache to output_dir. Assumes all downloads are retrieved.

    download_info is the DownloadInfo of downloads to unpack.
    cache_dir is the pathlib.Path directory containing the download cache
    components is a list of component names to unpack, if not empty.
    output_dir is the pathlib.Path directory to unpack the downloads to.
    extractors is a dictionary of PlatformEnum to a command or path to the
        extractor binary. Defaults to 'tar' for tar, and '_use_registry' for 7-Zip and WinRAR.

    May raise undetermined exceptions during archive unpacking.
    """
    for download_name, download_properties in download_info.properties_iter():
        if components and not download_name in components:
            continue
        download_path = cache_dir / download_properties.download_filename
        get_logger().info('Unpacking "%s" to %s ...', download_name,
                          download_properties.output_path)
        extractor_name = download_properties.extractor or ExtractorEnum.TAR
        if extractor_name == ExtractorEnum.SEVENZIP:
            extractor_func = extract_with_7z
        elif extractor_name == ExtractorEnum.WINRAR:
            extractor_func = extract_with_winrar
        elif extractor_name == ExtractorEnum.TAR:
            extractor_func = extract_tar_file
        else:
            raise NotImplementedError(extractor_name)

        if download_properties.strip_leading_dirs is None:
            strip_leading_dirs_path = None
        else:
            strip_leading_dirs_path = Path(download_properties.strip_leading_dirs)

        extractor_func(archive_path=download_path,
                       output_dir=output_dir / Path(download_properties.output_path),
                       relative_to=strip_leading_dirs_path,
                       extractors=extractors)


def _add_common_args(parser):
    parser.add_argument(
        '-i',
        '--ini',
        type=Path,
        nargs='+',
        help='The downloads INI to parse for downloads. Can be specified multiple times.')
    parser.add_argument('-c',
                        '--cache',
                        type=Path,
                        required=True,
                        help='Path to the directory to cache downloads.')


def _retrieve_callback(args):
    info = DownloadInfo(args.ini)
    info.check_sections_exist(args.components)
    retrieve_downloads(info, args.cache, args.components, args.show_progress,
                       args.disable_ssl_verification)
    try:
        check_downloads(info, args.cache, args.components)
    except HashMismatchError as exc:
        get_logger().error('File checksum does not match: %s', exc)
        sys.exit(1)


def _unpack_callback(args):
    if args.skip_unused or args.sysroot:
        get_logger().warning('The --skip-unused and --sysroot flags for downloads.py are'
                             ' no longer functional and will be removed in the future.')
    extractors = {
        ExtractorEnum.SEVENZIP: args.sevenz_path,
        ExtractorEnum.WINRAR: args.winrar_path,
        ExtractorEnum.TAR: args.tar_path,
    }
    info = DownloadInfo(args.ini)
    info.check_sections_exist(args.components)
    unpack_downloads(info, args.cache, args.components, args.output, extractors)


def main():
    """CLI Entrypoint"""
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_params(parser)
    subparsers = parser.add_subparsers(title='Download actions', dest='action')

    # retrieve
    retrieve_parser = subparsers.add_parser(
        'retrieve',
        help='Retrieve and check download files',
        description=('Retrieves and checks downloads without unpacking. '
                     'The downloader will attempt to use CLI command "curl". '
                     'If it is not present, Python\'s urllib will be used. However, only '
                     'the CLI-based downloaders can be resumed if the download is aborted.'))
    _add_common_args(retrieve_parser)
    retrieve_parser.add_argument('--components',
                                 nargs='+',
                                 metavar='COMP',
                                 help='Retrieve only these components. Default: all')
    retrieve_parser.add_argument('--hide-progress-bar',
                                 action='store_false',
                                 dest='show_progress',
                                 help='Hide the download progress.')
    retrieve_parser.add_argument(
        '--disable-ssl-verification',
        action='store_true',
        help='Disables certification verification for downloads using HTTPS.')
    retrieve_parser.set_defaults(callback=_retrieve_callback)

    def _default_extractor_path(name):
        return USE_REGISTRY if get_running_platform() == PlatformEnum.WINDOWS else name

    # unpack
    unpack_parser = subparsers.add_parser(
        'unpack',
        help='Unpack download files',
        description='Verifies hashes of and unpacks download files into the specified directory.')
    _add_common_args(unpack_parser)
    unpack_parser.add_argument('--components',
                               nargs='+',
                               metavar='COMP',
                               help='Unpack only these components. Default: all')
    unpack_parser.add_argument('--tar-path',
                               default='tar',
                               help=('(Linux and macOS only) Command or path to the BSD or GNU tar '
                                     'binary for extraction. Default: %(default)s'))
    unpack_parser.add_argument(
        '--7z-path',
        dest='sevenz_path',
        default=_default_extractor_path('7z'),
        help=('Command or path to 7-Zip\'s "7z" binary. If "_use_registry" is '
              'specified, determine the path from the registry. Default: %(default)s'))
    unpack_parser.add_argument(
        '--winrar-path',
        dest='winrar_path',
        default=USE_REGISTRY,
        help=('Command or path to WinRAR\'s "winrar" binary. If "_use_registry" is '
              'specified, determine the path from the registry. Default: %(default)s'))
    unpack_parser.add_argument('output', type=Path, help='The directory to unpack to.')
    unpack_parser.add_argument('--skip-unused', action='store_true', help='Deprecated')
    unpack_parser.add_argument('--sysroot', choices=('amd64', 'i386'), help='Deprecated')
    unpack_parser.set_defaults(callback=_unpack_callback)

    args = parser.parse_args()
    args.callback(args)


if __name__ == '__main__':
    main()
