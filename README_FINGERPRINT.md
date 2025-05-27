# Fingerprint Browser - Ungoogled Chromium with Enhanced Privacy

This is a fork of ungoogled-chromium with additional fingerprinting protection features.

## Features

This build includes comprehensive fingerprinting protection that can be controlled via command-line switches:

### Font Fingerprinting Protection
- Selectively blocks non-system fonts to reduce font fingerprinting
- Preserves system default fonts for compatibility
- Uses conservative approach (blocks only 25% of non-system fonts)

### User Agent Spoofing
- Customize browser brand and version
- Spoof operating system information
- Support for Chrome, Edge, Opera, Vivaldi brands

### Hardware Information Spoofing
- Customize reported CPU core count
- Deterministic based on fingerprint seed

### Canvas and WebGL Protection
- Adds noise to canvas operations
- Spoofs WebGL renderer information
- Deterministic noise based on fingerprint seed

### Audio Context Protection
- Adds deterministic noise to audio fingerprinting

## Command Line Usage

### Basic Fingerprint Seed
```bash
--fingerprint=12345
```
Sets the base seed for all fingerprinting protection.

### Platform Spoofing
```bash
--fingerprint-platform=windows
--fingerprint-platform=linux  
--fingerprint-platform=macos
```

### Browser Brand Spoofing
```bash
--fingerprint-brand=Chrome
--fingerprint-brand=Edge
--fingerprint-brand=Opera
--fingerprint-brand=Vivaldi
```

### Version Spoofing
```bash
--fingerprint-brand-version=134.0.6998.165
--fingerprint-platform-version=19.0.0
```

### Hardware Spoofing
```bash
--fingerprint-hardware-concurrency=8
```

## Example Usage

```bash
# Spoof as Chrome on Windows with 8 cores
chromium --fingerprint=12345 --fingerprint-platform=windows --fingerprint-brand=Chrome --fingerprint-hardware-concurrency=8

# Spoof as Edge on Linux
chromium --fingerprint=67890 --fingerprint-platform=linux --fingerprint-brand=Edge

# Spoof as Safari on macOS
chromium --fingerprint=54321 --fingerprint-platform=macos --fingerprint-brand=Safari
```

## Building

This project follows the standard ungoogled-chromium build process. See the main README.md for detailed build instructions.

### Quick Build Steps
1. Follow ungoogled-chromium documentation
2. Replace the ungoogled-chromium submodule URL with this repository
3. Build as normal

## Compatibility

- Based on Chromium 134.0.6998.165
- Compatible with Windows, Linux, and macOS
- Maintains compatibility with standard web content

## Privacy Notes

- All fingerprinting protection is deterministic based on the provided seed
- No random data is used to ensure reproducible results
- System fonts are never blocked to maintain compatibility
- Conservative approach minimizes website breakage

## Contributing

Please follow Chromium coding standards:
- Use English comments only
- Follow Chromium style guide
- Minimize changes to core functionality
- Test thoroughly before submitting

## License

Same as ungoogled-chromium (BSD-3-Clause) 