"""Optional REST API server for Gizmo features."""

from __future__ import annotations

from flask import Flask, jsonify, request

from modules import memory, rag_engine
from modules.backup_restore import create_backup, restore_backup
from modules.collab import create_session_share, join_session
from modules.feature_workflows import run_workflow
from modules.sso import test_connection
from modules.feature_flags import get_flags, set_flag
from modules.feedback import submit_feedback

app = Flask(__name__)


@app.post('/chat')
def chat_endpoint():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get('prompt', '')
    mem = memory.format_memory_context(prompt, top_k=4)
    rag = rag_engine.format_rag_context(prompt, top_k=3)
    return jsonify({"prompt": prompt, "memory": mem, "rag": rag, "response": "Use main web UI model endpoint for full generation."})


@app.get('/memory')
def memory_list():
    query = request.args.get('q', '')
    return jsonify(memory.retrieve_memory(query, top_k=10))


@app.get('/rag')
def rag_list():
    query = request.args.get('q', '')
    return jsonify(rag_engine.retrieve_context(query, top_k=5))


@app.get('/models')
def models():
    return jsonify({"router": "available via modules/model_router.py"})


@app.post('/session/<session_id>/invite')
def session_invite(session_id: str):
    data = request.get_json(force=True, silent=True) or {}
    token = create_session_share(session_id, role=data.get('role', 'Editor'), password=data.get('password', ''))
    return jsonify({"token": token})


@app.post('/session/join')
def session_join():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(join_session(data.get('token', ''), data.get('user_id', ''), data.get('password', '')))


@app.post('/workflow/run')
def workflow_run():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(run_workflow(data.get('id', ''), data.get('input_text', '')))


@app.get('/auth/oidc/callback')
def auth_callback():
    return jsonify({"status": "ok", "message": "OIDC callback placeholder"})


@app.get('/auth/sso/test')
def auth_sso_test():
    provider = request.args.get('provider', 'Google')
    client_id = request.args.get('client_id', '')
    client_secret = request.args.get('client_secret', '')
    return jsonify(test_connection(provider, client_id, client_secret, mock_mode=True))




@app.post('/flags/set')
def flags_set():
    data = request.get_json(force=True, silent=True) or {}
    set_flag(data.get('session_id', 'default_session'), data.get('name', ''), bool(data.get('enabled', False)))
    return jsonify({"status": "ok"})


@app.get('/flags')
def flags_get():
    return jsonify(get_flags(request.args.get('session_id', 'default_session')))


@app.post('/feedback')
def feedback_post():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(submit_feedback(data.get('user_id', 'anon'), data.get('session_id', 'default_session'), data.get('text', ''), data.get('file_path', '')))


@app.post('/backup')
def backup_post():
    """Create a full backup of user_data/ and return the zip file path."""
    msg, path = create_backup(include_all=True)
    if path:
        return jsonify({"status": "ok", "message": msg, "path": path})
    return jsonify({"status": "error", "message": msg}), 500


@app.post('/restore')
def restore_post():
    """Restore user data from an uploaded .zip backup."""
    data = request.get_json(force=True, silent=True) or {}
    zip_path = data.get('zip_path', '')
    pre_backup = bool(data.get('pre_backup', True))
    if not zip_path:
        return jsonify({"status": "error", "message": "zip_path is required"}), 400
    msg = restore_backup(zip_path, create_pre_restore_backup=pre_backup)
    ok = msg.startswith("✅")
    return jsonify({"status": "ok" if ok else "error", "message": msg}), 200 if ok else 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
