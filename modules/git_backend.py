"""
Git Backend for Gizmo AI v3.5.2
Location: /content/text-generation-webui/modules/git_backend.py

Provides REST API endpoints for git operations
"""

import os
import subprocess
from pathlib import Path
from flask import Blueprint, request, jsonify
import logging

# Create blueprint
git_bp = Blueprint('git', __name__, url_prefix='/git')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Repository path - this is your working directory
REPO_PATH = Path("/content/text-generation-webui")

def run_git_command(command, cwd=None):
    """
    Execute a git command and return the result
    """
    if cwd is None:
        cwd = REPO_PATH
    
    try:
        logger.info(f"Running git command in {cwd}: {command}")
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True if isinstance(command, str) else False,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        logger.error("Git command timed out")
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out',
            'returncode': -1
        }
    except Exception as e:
        logger.error(f"Git command error: {e}")
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

@git_bp.route('/status', methods=['GET'])
def get_status():
    """
    Get git status information
    """
    try:
        # Get current branch
        branch_result = run_git_command('git branch --show-current')
        branch = branch_result['stdout'] if branch_result['success'] else 'unknown'
        
        # Get modified files
        modified_result = run_git_command('git diff --name-only')
        modified_files = [f for f in modified_result['stdout'].split('\n') if f] if modified_result['success'] else []
        
        # Get untracked files
        untracked_result = run_git_command('git ls-files --others --exclude-standard')
        untracked_files = [f for f in untracked_result['stdout'].split('\n') if f] if untracked_result['success'] else []
        
        # Get staged files
        staged_result = run_git_command('git diff --cached --name-only')
        staged_files = [f for f in staged_result['stdout'].split('\n') if f] if staged_result['success'] else []
        
        return jsonify({
            'ok': True,
            'branch': branch,
            'modified': modified_files,
            'untracked': untracked_files,
            'staged': staged_files
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@git_bp.route('/pull', methods=['POST'])
def pull_changes():
    """
    Pull latest changes from remote
    """
    try:
        # Get current branch
        result = run_git_command('git branch --show-current')
        if not result['success']:
            return jsonify({'ok': False, 'error': 'Could not determine current branch'}), 500
        
        branch = result['stdout']
        
        # Pull changes
        result = run_git_command(f'git pull origin {branch}')
        
        if result['success']:
            return jsonify({
                'ok': True,
                'message': result['stdout'],
                'branch': branch
            })
        else:
            return jsonify({
                'ok': False,
                'error': result['stderr'] or result['stdout'] or 'Pull failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Error pulling changes: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@git_bp.route('/push', methods=['POST'])
def push_changes():
    """
    Commit and push changes
    Expects JSON: { "branch": "branch-name", "message": "commit message" }
    """
    try:
        data = request.get_json() or {}
        branch = data.get('branch', '').strip()
        message = data.get('message', 'Update from Gizmo AI').strip()
        
        # Get current branch if not specified
        if not branch:
            result = run_git_command('git branch --show-current')
            if result['success']:
                branch = result['stdout']
            else:
                return jsonify({'ok': False, 'error': 'Could not determine current branch'}), 500
        
        # Stage all changes
        result = run_git_command('git add -A')
        if not result['success']:
            return jsonify({'ok': False, 'error': f'Failed to stage changes: {result["stderr"]}'}), 500
        
        # Check if there are changes to commit
        result = run_git_command('git diff --cached --quiet')
        if result['returncode'] == 0:
            return jsonify({'ok': True, 'message': 'No changes to commit', 'already_up_to_date': True})
        
        # Commit changes
        # Escape the message properly
        safe_message = message.replace('"', '\\"')
        commit_cmd = f'git commit -m "{safe_message}"'
        result = run_git_command(commit_cmd)
        if not result['success']:
            return jsonify({'ok': False, 'error': f'Failed to commit: {result["stderr"]}'}), 500
        
        # Push to remote
        push_cmd = f'git push origin {branch}'
        result = run_git_command(push_cmd)
        
        if result['success']:
            return jsonify({
                'ok': True,
                'message': f'Successfully pushed to {branch}',
                'branch': branch
            })
        else:
            return jsonify({
                'ok': False,
                'error': result['stderr'] or result['stdout'] or 'Push failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Error pushing changes: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@git_bp.route('/create-branch', methods=['POST'])
def create_branch():
    """
    Create a new git branch
    Expects JSON: { "branch": "branch-name", "base": "base-branch" }
    """
    try:
        data = request.get_json() or {}
        branch_name = data.get('branch', '').strip()
        base_branch = data.get('base', 'main').strip()
        
        if not branch_name:
            return jsonify({'ok': False, 'error': 'Branch name is required'}), 400
        
        # Validate branch name
        if ' ' in branch_name or '..' in branch_name:
            return jsonify({'ok': False, 'error': 'Invalid branch name'}), 400
        
        # Check if branch already exists
        result = run_git_command(f'git branch --list {branch_name}')
        if result['success'] and result['stdout']:
            return jsonify({'ok': False, 'error': f'Branch {branch_name} already exists'}), 400
        
        # Create the branch
        result = run_git_command(f'git checkout -b {branch_name} {base_branch}')
        
        if result['success']:
            return jsonify({
                'ok': True,
                'branch': branch_name,
                'message': f'Branch {branch_name} created from {base_branch}'
            })
        else:
            return jsonify({
                'ok': False,
                'error': result['stderr'] or result['stdout'] or 'Failed to create branch'
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

def init_git_routes(app):
    """
    Initialize git routes in the Flask app
    Call this from your server.py or main app file
    """
    app.register_blueprint(git_bp)
    logger.info("Git routes initialized for Gizmo v3.5.2")
    print("[✓] Git API routes registered at /git/*")
