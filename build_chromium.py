#!/usr/bin/env python3
"""
Ungoogled Chromium Build Script
Automates the build process for the refactored ungoogled-chromium project.
"""

import os
import sys
import subprocess
import argparse
import platform
import shutil
from pathlib import Path

class ChromiumBuilder:
    def __init__(self):
        self.system = platform.system().lower()
        self.script_dir = Path(__file__).parent.absolute()
        self.build_dir = self.script_dir / "out" / "Release"
        
    def check_prerequisites(self):
        """Check if required tools are available."""
        required_tools = ['git', 'python3']
        
        if self.system == 'windows':
            required_tools.extend(['cmd'])
        else:
            required_tools.extend(['ninja', 'gn'])
            
        missing_tools = []
        for tool in required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)
                
        if missing_tools:
            print(f"Error: Missing required tools: {', '.join(missing_tools)}")
            print("Please install the missing tools and try again.")
            return False
            
        return True
        
    def setup_environment(self):
        """Set up build environment variables."""
        env = os.environ.copy()
        
        if self.system == 'windows':
            env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
            env['GYP_MSVS_VERSION'] = '2022'
            
        return env
        
    def apply_patches(self):
        """Apply ungoogled-chromium patches."""
        print("Applying patches...")
        
        patches_dir = self.script_dir / "patches"
        series_file = patches_dir / "series"
        
        if not series_file.exists():
            print("Error: patches/series file not found!")
            return False
            
        try:
            with open(series_file, 'r', encoding='utf-8') as f:
                patches = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
            for patch in patches:
                patch_path = patches_dir / patch
                if not patch_path.exists():
                    print(f"Warning: Patch file {patch} not found, skipping...")
                    continue
                    
                print(f"Applying patch: {patch}")
                result = subprocess.run(['git', 'apply', str(patch_path)], 
                                      capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"Error applying patch {patch}:")
                    print(result.stderr)
                    return False
                    
        except Exception as e:
            print(f"Error reading patches: {e}")
            return False
            
        print("All patches applied successfully!")
        return True
        
    def configure_build(self, args):
        """Configure the build using GN."""
        print("Configuring build...")
        
        # Create build directory
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        # Read base flags
        flags_file = self.script_dir / "flags.gn"
        base_flags = []
        
        if flags_file.exists():
            with open(flags_file, 'r', encoding='utf-8') as f:
                base_flags = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Add custom flags
        custom_flags = []
        
        if args.debug:
            custom_flags.append('is_debug=true')
        else:
            custom_flags.append('is_debug=false')
            
        if args.official:
            custom_flags.append('is_official_build=true')
            
        if args.component_build:
            custom_flags.append('is_component_build=true')
            
        # Combine all flags
        all_flags = base_flags + custom_flags
        gn_args = ' '.join(all_flags)
        
        # Run GN
        env = self.setup_environment()
        cmd = ['gn', 'gen', str(self.build_dir), f'--args={gn_args}']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Error configuring build:")
            print(result.stderr)
            return False
            
        print("Build configured successfully!")
        return True
        
    def build_chromium(self, args):
        """Build Chromium using Ninja."""
        print("Building Chromium...")
        
        env = self.setup_environment()
        
        # Determine number of parallel jobs
        jobs = args.jobs if args.jobs else os.cpu_count()
        
        cmd = ['ninja', '-C', str(self.build_dir), '-j', str(jobs)]
        
        if args.target:
            cmd.append(args.target)
        else:
            cmd.append('chrome')
            
        print(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, env=env)
            
            if result.returncode == 0:
                print("Build completed successfully!")
                print(f"Output directory: {self.build_dir}")
                return True
            else:
                print("Build failed!")
                return False
                
        except KeyboardInterrupt:
            print("\nBuild interrupted by user.")
            return False
        except Exception as e:
            print(f"Build error: {e}")
            return False
            
    def clean_build(self):
        """Clean build directory."""
        print("Cleaning build directory...")
        
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
            print("Build directory cleaned.")
        else:
            print("Build directory doesn't exist.")
            
    def run_tests(self):
        """Run basic tests."""
        print("Running tests...")
        
        test_binary = self.build_dir / "unit_tests"
        if self.system == 'windows':
            test_binary = test_binary.with_suffix('.exe')
            
        if test_binary.exists():
            result = subprocess.run([str(test_binary)], capture_output=True)
            if result.returncode == 0:
                print("Tests passed!")
                return True
            else:
                print("Some tests failed.")
                return False
        else:
            print("Test binary not found. Skipping tests.")
            return True

def main():
    parser = argparse.ArgumentParser(description='Build Ungoogled Chromium')
    
    parser.add_argument('--clean', action='store_true', 
                       help='Clean build directory before building')
    parser.add_argument('--debug', action='store_true',
                       help='Build debug version')
    parser.add_argument('--official', action='store_true',
                       help='Build official release version')
    parser.add_argument('--component-build', action='store_true',
                       help='Build as component build (faster incremental builds)')
    parser.add_argument('--jobs', '-j', type=int,
                       help='Number of parallel build jobs')
    parser.add_argument('--target', type=str, default='chrome',
                       help='Build target (default: chrome)')
    parser.add_argument('--no-patches', action='store_true',
                       help='Skip applying patches (assume already applied)')
    parser.add_argument('--test', action='store_true',
                       help='Run tests after building')
    parser.add_argument('--configure-only', action='store_true',
                       help='Only configure build, do not compile')
    
    args = parser.parse_args()
    
    builder = ChromiumBuilder()
    
    # Check prerequisites
    if not builder.check_prerequisites():
        sys.exit(1)
        
    # Clean if requested
    if args.clean:
        builder.clean_build()
        
    # Apply patches unless skipped
    if not args.no_patches:
        if not builder.apply_patches():
            print("Failed to apply patches!")
            sys.exit(1)
            
    # Configure build
    if not builder.configure_build(args):
        print("Failed to configure build!")
        sys.exit(1)
        
    # Build unless configure-only
    if not args.configure_only:
        if not builder.build_chromium(args):
            print("Build failed!")
            sys.exit(1)
            
        # Run tests if requested
        if args.test:
            if not builder.run_tests():
                print("Tests failed!")
                sys.exit(1)
                
    print("All operations completed successfully!")

if __name__ == '__main__':
    main() 