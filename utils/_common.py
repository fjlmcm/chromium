# -*- coding: UTF-8 -*-

# Copyright (c) 2020 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Common code and constants"""
import argparse
import enum
import logging
import platform
from pathlib import Path

# Constants
ENCODING = 'UTF-8'  # For config files and patches
USE_REGISTRY = '_use_registry'
LOGGER_NAME = 'ungoogled'

# Default logging configuration
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(levelname)s: %(message)s'

# Logging level mappings
LOG_LEVEL_MAP = {
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG
}

# Public classes

class PlatformEnum(enum.Enum):
    """Enum for platforms that need distinction for certain functionality"""
    UNIX = 'unix'     # Currently covers anything that isn't Windows
    WINDOWS = 'windows'


class ExtractorEnum:  # pylint: disable=too-few-public-methods
    """Enum for extraction binaries"""
    SEVENZIP = '7z'
    TAR = 'tar'
    WINRAR = 'winrar'


class SetLogLevel(argparse.Action):  # pylint: disable=too-few-public-methods
    """Sets logging level based on command line arguments it receives"""

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        """Handle the logging level setting action"""
        if option_string in ('--verbose', '-v'):
            level = logging.DEBUG
        elif option_string in ('--quiet', '-q'):
            level = logging.ERROR
        else:
            level = LOG_LEVEL_MAP.get(value, DEFAULT_LOG_LEVEL)
        
        set_logging_level(level)

# Public methods

def get_logger(initial_level=None):
    """
    Gets the named logger with appropriate configuration
    
    Args:
        initial_level: Initial logging level (defaults to DEFAULT_LOG_LEVEL)
    
    Returns:
        Configured logger instance
    """
    if initial_level is None:
        initial_level = DEFAULT_LOG_LEVEL
        
    logger = logging.getLogger(LOGGER_NAME)
    
    if logger.level == logging.NOTSET:
        logger.setLevel(initial_level)
        
        if not logger.hasHandlers():
            console_handler = logging.StreamHandler()
            console_handler.setLevel(initial_level)
            
            formatter = logging.Formatter(LOG_FORMAT)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(console_handler)
    
    return logger


def set_logging_level(logging_level):
    """
    Sets logging level of logger and all its handlers
    
    Args:
        logging_level: Target logging level
        
    Returns:
        Configured logger instance
    """
    if not logging_level:
        logging_level = DEFAULT_LOG_LEVEL
    
    logger = get_logger()
    logger.setLevel(logging_level)
    
    for handler in logger.handlers:
        handler.setLevel(logging_level)
    
    return logger


def get_running_platform():
    """
    Returns a PlatformEnum value indicating the platform that utils is running on.
    
    NOTE: Platform detection should only be used when no cross-platform alternative is available.
    
    Returns:
        PlatformEnum value representing the current platform
    """
    uname = platform.uname()
    # Detect native python and WSL
    if uname.system == 'Windows' or 'Microsoft' in uname.release:
        return PlatformEnum.WINDOWS
    # Only Windows and UNIX-based platforms need to be distinguished right now.
    return PlatformEnum.UNIX


def get_chromium_version():
    """
    Returns the Chromium version from chromium_version.txt
    
    Returns:
        String containing the Chromium version
        
    Raises:
        FileNotFoundError: If chromium_version.txt does not exist
        IOError: If file cannot be read
    """
    version_file = Path(__file__).parent.parent / 'chromium_version.txt'
    try:
        return version_file.read_text(encoding=ENCODING).strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Chromium version file not found: {version_file}") from exc
    except IOError as exc:
        raise IOError(f"Cannot read chromium version file: {version_file}") from exc


def parse_series(series_path):
    """
    Returns an iterator of paths over the series file
    
    Args:
        series_path: pathlib.Path to the series file
        
    Yields:
        String paths from the series file (comments and blank lines filtered)
        
    Raises:
        FileNotFoundError: If series file does not exist
        IOError: If file cannot be read
    """
    try:
        with series_path.open(encoding=ENCODING) as series_file:
            series_lines = series_file.read().splitlines()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Series file not found: {series_path}") from exc
    except IOError as exc:
        raise IOError(f"Cannot read series file: {series_path}") from exc
    
    # Filter blank lines and comments, strip inline comments
    series_lines = (line.strip().split(' #')[0] for line in series_lines 
                   if line.strip() and not line.strip().startswith('#'))
    
    return series_lines


def add_common_params(parser):
    """
    Adds common command line arguments to a parser.
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    # Logging levels
    logging_group = parser.add_mutually_exclusive_group()
    
    logging_group.add_argument(
        '--log-level',
        action=SetLogLevel,
        choices=list(LOG_LEVEL_MAP.keys()),
        help="Set logging level of current script. Only one of 'log-level', 'verbose', "
             "'quiet' can be set at a time."
    )
    
    logging_group.add_argument(
        '--quiet', '-q',
        action=SetLogLevel,
        nargs=0,
        help="Display less outputs to console. Only one of 'log-level', 'verbose', "
             "'quiet' can be set at a time."
    )
    
    logging_group.add_argument(
        '--verbose', '-v',
        action=SetLogLevel,
        nargs=0,
        help="Increase logging verbosity to include DEBUG messages. Only one of "
             "'log-level', 'verbose', 'quiet' can be set at a time."
    )
