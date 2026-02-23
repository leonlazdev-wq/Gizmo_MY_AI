"""Optional REST API server for Gizmo features."""

from __future__ import annotations

from flask import Flask, jsonify, request

from modules import memory, rag_engine, collab, auth, sso

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


@app.post('/session/<sid>/invite')
def session_invite(sid):
    data = request.get_json(force=True, silent=True) or {}
    owner = data.get('owner_id', 'owner')
    token = collab.create_session_share(sid, owner_id=owner, password=data.get('password', ''))
    return jsonify({"token": token, "expires_in_hours": 24})


@app.post('/session/join')
def session_join():
    data = request.get_json(force=True, silent=True) or {}
    result = collab.join_session(data.get('token', ''), data.get('user_id', ''), data.get('password', ''))
    return jsonify(result)


@app.get('/session/<sid>/collaborators')
def session_collaborators(sid):
    return jsonify(collab.list_collaborators(sid))


@app.get('/auth/sso/test')
def sso_test_endpoint():
    provider = request.args.get('provider', 'Google')
    client_id = request.args.get('client_id', '')
    client_secret = request.args.get('client_secret', '')
    return jsonify(sso.run_sso_test(provider, client_id, client_secret, mock_mode=True))


@app.get('/auth/oidc/callback')
def oidc_callback():
    return jsonify({"ok": True, "message": "OIDC callback received (mock)."})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
