"""Optional REST API server for Gizmo features."""

from __future__ import annotations

from flask import Flask, jsonify, request

from modules import memory, rag_engine

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
