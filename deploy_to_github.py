#!/usr/bin/env python3
"""
Deploy Refactored Ungoogled Chromium to GitHub
Automates the process of pushing the refactored code to the target repository.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import datetime

class GitDeployer:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.target_repo = "https://github.com/fjlmcm/chromium.git"
        self.target_tag = "134.0.6998.165"
        
    def check_git_status(self):
        """Check if git repository is clean and ready for deployment."""
        try:
            # Check if we're in a git repository
            result = subprocess.run(['git', 'rev-parse', '--git-dir'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("Error: Not in a git repository!")
                return False
                
            # Check for uncommitted changes
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                print("Warning: There are uncommitted changes:")
                print(result.stdout)
                response = input("Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    return False
                    
            return True
            
        except Exception as e:
            print(f"Error checking git status: {e}")
            return False
            
    def setup_remote(self, force=False):
        """Set up the target remote repository."""
        try:
            # Check if remote already exists
            result = subprocess.run(['git', 'remote', 'get-url', 'target'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                if force:
                    print("Updating existing remote...")
                    subprocess.run(['git', 'remote', 'set-url', 'target', self.target_repo])
                else:
                    print(f"Remote 'target' already exists: {result.stdout.strip()}")
                    if result.stdout.strip() != self.target_repo:
                        response = input(f"Update remote URL to {self.target_repo}? (y/N): ")
                        if response.lower() == 'y':
                            subprocess.run(['git', 'remote', 'set-url', 'target', self.target_repo])
            else:
                print(f"Adding remote 'target': {self.target_repo}")
                subprocess.run(['git', 'remote', 'add', 'target', self.target_repo])
                
            return True
            
        except Exception as e:
            print(f"Error setting up remote: {e}")
            return False
            
    def create_commit(self, message=None):
        """Create a commit with all changes."""
        try:
            # Add all files
            subprocess.run(['git', 'add', '.'])
            
            # Create commit message
            if not message:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"Refactor ungoogled-chromium for {self.target_tag}\n\n" \
                         f"- Remove Chinese comments and improve code quality\n" \
                         f"- Enhance font fingerprinting protection\n" \
                         f"- Improve cross-platform compatibility\n" \
                         f"- Follow Chromium coding standards\n\n" \
                         f"Refactored on: {timestamp}"
                         
            # Create commit
            result = subprocess.run(['git', 'commit', '-m', message], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("Commit created successfully!")
                return True
            elif "nothing to commit" in result.stdout:
                print("No changes to commit.")
                return True
            else:
                print(f"Error creating commit: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error creating commit: {e}")
            return False
            
    def create_tag(self, force=False):
        """Create and push the target tag."""
        try:
            # Check if tag already exists
            result = subprocess.run(['git', 'tag', '-l', self.target_tag], 
                                  capture_output=True, text=True)
            
            if result.stdout.strip():
                if force:
                    print(f"Deleting existing tag: {self.target_tag}")
                    subprocess.run(['git', 'tag', '-d', self.target_tag])
                else:
                    print(f"Tag {self.target_tag} already exists!")
                    response = input("Delete and recreate? (y/N): ")
                    if response.lower() != 'y':
                        return True
                    subprocess.run(['git', 'tag', '-d', self.target_tag])
                    
            # Create new tag
            tag_message = f"Refactored Ungoogled Chromium {self.target_tag}\n\n" \
                         f"This release includes:\n" \
                         f"- Enhanced fingerprinting protection\n" \
                         f"- Improved code quality and standards compliance\n" \
                         f"- Better cross-platform support\n" \
                         f"- System font preservation in font fingerprinting"
                         
            result = subprocess.run(['git', 'tag', '-a', self.target_tag, '-m', tag_message], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Tag {self.target_tag} created successfully!")
                return True
            else:
                print(f"Error creating tag: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error creating tag: {e}")
            return False
            
    def push_to_remote(self, force=False):
        """Push commits and tags to the target repository."""
        try:
            # Push commits
            push_cmd = ['git', 'push', 'target', 'HEAD:main']
            if force:
                push_cmd.append('--force')
                
            print("Pushing commits to target repository...")
            result = subprocess.run(push_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error pushing commits: {result.stderr}")
                return False
                
            # Push tags
            tag_push_cmd = ['git', 'push', 'target', self.target_tag]
            if force:
                tag_push_cmd.append('--force')
                
            print(f"Pushing tag {self.target_tag}...")
            result = subprocess.run(tag_push_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error pushing tag: {result.stderr}")
                return False
                
            print("Successfully pushed to target repository!")
            return True
            
        except Exception as e:
            print(f"Error pushing to remote: {e}")
            return False
            
    def verify_deployment(self):
        """Verify that the deployment was successful."""
        try:
            print("Verifying deployment...")
            
            # Fetch from target remote
            subprocess.run(['git', 'fetch', 'target'], capture_output=True)
            
            # Check if tag exists on remote
            result = subprocess.run(['git', 'ls-remote', '--tags', 'target', self.target_tag], 
                                  capture_output=True, text=True)
            
            if result.stdout.strip():
                print(f"✓ Tag {self.target_tag} found on remote repository")
                return True
            else:
                print(f"✗ Tag {self.target_tag} not found on remote repository")
                return False
                
        except Exception as e:
            print(f"Error verifying deployment: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Deploy refactored ungoogled-chromium to GitHub')
    
    parser.add_argument('--force', action='store_true',
                       help='Force push (overwrite remote changes)')
    parser.add_argument('--message', '-m', type=str,
                       help='Custom commit message')
    parser.add_argument('--no-commit', action='store_true',
                       help='Skip creating new commit')
    parser.add_argument('--no-tag', action='store_true',
                       help='Skip creating/updating tag')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify the current deployment status')
    
    args = parser.parse_args()
    
    deployer = GitDeployer()
    
    if args.verify_only:
        if deployer.verify_deployment():
            print("Deployment verification successful!")
        else:
            print("Deployment verification failed!")
            sys.exit(1)
        return
    
    if args.dry_run:
        print("DRY RUN MODE - No actual changes will be made")
        print(f"Target repository: {deployer.target_repo}")
        print(f"Target tag: {deployer.target_tag}")
        print("Operations that would be performed:")
        if not args.no_commit:
            print("- Create commit with current changes")
        if not args.no_tag:
            print(f"- Create/update tag {deployer.target_tag}")
        print("- Push to target repository")
        return
    
    # Check git status
    if not deployer.check_git_status():
        print("Git repository check failed!")
        sys.exit(1)
        
    # Set up remote
    if not deployer.setup_remote(force=args.force):
        print("Failed to set up remote repository!")
        sys.exit(1)
        
    # Create commit if requested
    if not args.no_commit:
        if not deployer.create_commit(args.message):
            print("Failed to create commit!")
            sys.exit(1)
            
    # Create tag if requested
    if not args.no_tag:
        if not deployer.create_tag(force=args.force):
            print("Failed to create tag!")
            sys.exit(1)
            
    # Push to remote
    if not deployer.push_to_remote(force=args.force):
        print("Failed to push to remote repository!")
        sys.exit(1)
        
    # Verify deployment
    if not deployer.verify_deployment():
        print("Deployment verification failed!")
        sys.exit(1)
        
    print("\n" + "="*50)
    print("DEPLOYMENT SUCCESSFUL!")
    print("="*50)
    print(f"Repository: {deployer.target_repo}")
    print(f"Tag: {deployer.target_tag}")
    print(f"Branch: main")
    print("\nThe refactored ungoogled-chromium has been successfully deployed!")

if __name__ == '__main__':
    main() 