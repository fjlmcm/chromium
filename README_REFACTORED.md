# Ungoogled Chromium Fingerprint Browser - Refactored

*A refactored version of ungoogled-chromium with enhanced fingerprint protection*

## Refactoring Objectives

This refactored version addresses the following improvements:

1. **Code Quality**: All code now follows Chromium coding standards
2. **Internationalization**: Removed all Chinese comments and replaced with English
3. **Font Protection**: Enhanced font fingerprinting to preserve system default fonts
4. **Build Compliance**: Ensured compatibility with Chromium 134.0.6998.165

## Key Improvements

### Font Fingerprinting Enhancement

The font fingerprinting mechanism has been improved to:
- **Preserve System Fonts**: System default fonts (Arial, Times New Roman, Helvetica, etc.) are never blocked
- **Selective Blocking**: Only non-system fonts are subject to fingerprinting protection
- **Deterministic Behavior**: Uses fingerprint seed for consistent behavior across sessions

### Code Quality Improvements

- **Chromium Compliance**: All code follows Chromium C++ style guide
- **English Comments**: All comments are now in English for international collaboration
- **Proper Naming**: Function and variable names follow Chromium conventions
- **Header Guards**: Proper include guards and forward declarations

### Enhanced Fingerprint Protection

The refactored version includes improved protection for:
- **User Agent**: Platform-aware user agent spoofing
- **Hardware Concurrency**: Configurable CPU core reporting
- **Audio Context**: Audio fingerprint protection with deterministic offsets
- **WebGL Info**: Comprehensive GPU information spoofing
- **Canvas**: Enhanced canvas fingerprint protection

## Build Instructions

This refactored version is designed to be built using the standard ungoogled-chromium process:

```bash
# Replace the ungoogled-chromium submodule URL with this repository
git clone https://github.com/fjlmcm/chromium.git
cd chromium
git checkout 134.0.6998.165

# Follow standard ungoogled-chromium build process
# Apply patches in order specified in patches/series
./utils/patches.py apply src patches

# Configure and build
mkdir -p out/Default
cp flags.gn out/Default/args.gn
gn gen out/Default
ninja -C out/Default chrome
```

## Configuration Options

The refactored version supports the following command-line switches:

- `--fingerprint=<seed>`: Base fingerprint seed for all spoofing
- `--fingerprint-platform=<platform>`: Target platform (windows/linux/macos)
- `--fingerprint-platform-version=<version>`: Platform version override
- `--fingerprint-brand=<brand>`: Browser brand (Chrome/Edge/Opera/Vivaldi)
- `--fingerprint-brand-version=<version>`: Browser version override
- `--fingerprint-hardware-concurrency=<cores>`: CPU core count override

## Font Protection Details

The enhanced font protection works as follows:

1. **System Font Whitelist**: A comprehensive list of system default fonts is maintained
2. **Selective Blocking**: Only fonts not in the whitelist are subject to fingerprinting
3. **Deterministic Algorithm**: Uses the fingerprint seed to determine which fonts to block
4. **Cross-Platform Support**: Works consistently across Windows, Linux, and macOS

### Whitelisted System Fonts

- Arial, Times New Roman, Courier New
- Helvetica, Times, Courier
- Georgia, Verdana, Tahoma
- Trebuchet MS, Impact, Comic Sans MS
- Palatino, Lucida Grande, Lucida Sans Unicode

## Compliance and Standards

This refactored version ensures:

- **No Chinese Text**: All user-facing text and comments are in English
- **Line Endings**: Consistent LF line endings across all files
- **UTF-8 Encoding**: All files use UTF-8 encoding
- **Chromium Style**: Follows Chromium C++ style guide
- **Build Compatibility**: Compatible with Chromium 134.0.6998.165

## Contributing

When contributing to this refactored version:

1. Follow Chromium coding standards
2. Use English for all comments and documentation
3. Test on multiple platforms (Windows, Linux, macOS)
4. Ensure font protection doesn't break system fonts
5. Maintain compatibility with ungoogled-chromium build system

## License

This refactored version maintains the same BSD-3-clause license as the original ungoogled-chromium project.

## Acknowledgments

- Original ungoogled-chromium project and contributors
- Chromium project for coding standards and guidelines
- Community feedback for font protection improvements 