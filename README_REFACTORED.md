# Ungoogled Chromium Fingerprint Browser - Refactored

*A privacy-focused Chromium fork with advanced fingerprinting protection*

## Project Overview

This is a refactored version of the Ungoogled Chromium project with enhanced fingerprinting protection capabilities. The project has been restructured to comply with Chromium coding standards and improve maintainability.

## Version Information

- **Chromium Version**: 134.0.6998.165
- **Target Repository**: https://github.com/fjlmcm/chromium
- **Target Tag**: 134.0.6998.165

## Key Improvements in This Refactor

### 1. Code Quality Enhancements
- **Removed Chinese comments**: All Chinese comments have been replaced with English equivalents
- **Improved code structure**: Better organization and readability
- **Chromium coding standards compliance**: Follows official Chromium style guidelines
- **Consistent formatting**: Proper line endings and indentation

### 2. Enhanced Font Fingerprinting Protection
- **System font preservation**: System default fonts are no longer blocked
- **Expanded system font list**: Includes common fonts across Windows, Linux, and macOS
- **Intelligent filtering**: Only non-system fonts are subject to fingerprinting protection
- **Reduced blocking probability**: Changed from 50% to 30% for better usability

### 3. Improved Fingerprinting Features
- **Deterministic behavior**: All fingerprinting uses seed-based deterministic algorithms
- **Cross-platform compatibility**: Proper handling for Windows, Linux, and macOS
- **Consistent API**: Unified command-line interface for all fingerprinting features

## Fingerprinting Protection Features

### Font Fingerprinting
- Protects against font enumeration attacks
- Preserves system default fonts for compatibility
- Uses deterministic blocking based on fingerprint seed

### User Agent Fingerprinting
- Customizable browser brand and version
- Platform-specific user agent strings
- Support for Chrome, Edge, Opera, Vivaldi, and custom brands

### Hardware Fingerprinting
- Configurable CPU core count
- Fixed device memory reporting
- GPU information spoofing with platform-specific models

### Canvas Fingerprinting
- Deterministic noise injection
- Client rectangle protection
- Image data shuffling with seed-based randomization

## Command Line Options

### Basic Fingerprinting
```bash
--fingerprint=<seed>                    # Base fingerprint seed (required for most features)
```

### Platform Spoofing
```bash
--fingerprint-platform=<platform>      # windows, linux, or macos
--fingerprint-platform-version=<ver>   # Custom platform version
```

### Browser Brand Spoofing
```bash
--fingerprint-brand=<brand>            # Chrome, Edge, Opera, Vivaldi, or custom
--fingerprint-brand-version=<version>  # Custom brand version
```

### Hardware Spoofing
```bash
--fingerprint-hardware-concurrency=<n> # Number of CPU cores to report
```

## Build Instructions

1. **Download Chromium source code** for version 134.0.6998.165
2. **Apply patches** from this repository in the order specified in `patches/series`
3. **Configure build** using the provided `flags.gn`
4. **Build** using standard Chromium build process

### Example Build Commands (Windows)
```cmd
# Set up build environment
set DEPOT_TOOLS_WIN_TOOLCHAIN=0
set GYP_MSVS_VERSION=2022

# Configure build
gn gen out/Release --args="import(\"//flags.gn\")"

# Build
ninja -C out/Release chrome
```

## Usage Examples

### Basic Privacy Protection
```bash
chrome.exe --fingerprint=123456789
```

### Simulate Windows Chrome
```bash
chrome.exe --fingerprint=123456789 --fingerprint-platform=windows --fingerprint-brand=Chrome
```

### Simulate macOS Safari-like
```bash
chrome.exe --fingerprint=987654321 --fingerprint-platform=macos --fingerprint-brand=Safari
```

### Custom Configuration
```bash
chrome.exe --fingerprint=555666777 \
  --fingerprint-platform=linux \
  --fingerprint-brand=Firefox \
  --fingerprint-brand-version=120.0 \
  --fingerprint-hardware-concurrency=8
```

## Technical Details

### Patch Organization
- **Core patches**: Essential ungoogling and privacy features
- **Extra patches**: Additional privacy enhancements and fingerprinting protection
- **Fingerprint patches**: Specific fingerprinting protection modules

### Key Components
- **Font Cache Modification**: Enhanced font enumeration protection
- **User Agent Spoofing**: Comprehensive user agent string manipulation
- **Canvas Protection**: Advanced canvas fingerprinting countermeasures
- **WebGL Spoofing**: GPU information randomization
- **Hardware Spoofing**: CPU and memory information control

### Compatibility
- **Windows**: Full support for Windows 10/11
- **Linux**: Tested on Ubuntu, Debian, and derivatives
- **macOS**: Support for macOS 10.15+ (Intel and Apple Silicon)

## Security Considerations

### Fingerprinting Protection Levels
1. **Basic**: Font and canvas protection with default settings
2. **Enhanced**: Full platform and browser spoofing
3. **Advanced**: Custom hardware configuration and detailed spoofing

### Privacy Features
- **No Google services**: All Google service dependencies removed
- **No telemetry**: Crash reporting and usage statistics disabled
- **Enhanced privacy**: Additional privacy-focused modifications

## Contributing

### Code Standards
- Follow Chromium coding style guidelines
- Use English comments only
- Maintain cross-platform compatibility
- Test on all supported platforms

### Patch Guidelines
- Keep patches focused and minimal
- Document all changes thoroughly
- Ensure patches apply cleanly
- Test functionality after applying patches

## License

This project inherits the BSD-3-Clause license from Chromium and Ungoogled Chromium.

## Acknowledgments

- **The Chromium Project**: For the base browser engine
- **Ungoogled Chromium**: For the foundation of Google service removal
- **Community Contributors**: For testing, feedback, and improvements

## Support

For issues and questions:
1. Check existing issues in the repository
2. Review the documentation thoroughly
3. Test with minimal configuration first
4. Provide detailed reproduction steps when reporting issues

---

*This refactored version maintains all the privacy and fingerprinting protection features while improving code quality and maintainability.* 