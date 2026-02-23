import gradio as gr

from modules import rag_engine, shared
from modules.utils import gradio


def create_ui():
    with gr.Tab("Knowledge Base", elem_id="knowledge-base-tab"):
        gr.Markdown("## Knowledge Base")
        shared.gradio['kb_file'] = gr.File(label='Upload document', file_count='single', type='filepath')
        shared.gradio['kb_ingest'] = gr.Button('Ingest document', variant='primary')
        shared.gradio['kb_docs'] = gr.Dropdown(label='Indexed documents', choices=rag_engine.list_documents(), value=None)
        with gr.Row():
            shared.gradio['kb_delete'] = gr.Button('Delete selected document')
            shared.gradio['kb_reindex'] = gr.Button('Reindex all')

        shared.gradio['kb_query'] = gr.Textbox(label='Search query')
        shared.gradio['kb_search'] = gr.Button('Search KB')
        shared.gradio['kb_status'] = gr.Textbox(label='Status', interactive=False)
        shared.gradio['kb_results'] = gr.Textbox(label='Results', lines=12)


def create_event_handlers():
    shared.gradio['kb_ingest'].click(
        lambda path: (f"✅ Ingested {rag_engine.ingest_file(path)} chunks", gr.update(choices=rag_engine.list_documents())),
        gradio('kb_file'),
        gradio('kb_status', 'kb_docs'),
        show_progress=False,
    )

    shared.gradio['kb_delete'].click(
        lambda name: (f"✅ Deleted {rag_engine.delete_document(name)} chunks", gr.update(choices=rag_engine.list_documents())),
        gradio('kb_docs'),
        gradio('kb_status', 'kb_docs'),
        show_progress=False,
    )

    shared.gradio['kb_reindex'].click(
        lambda: f"✅ Reindexed {rag_engine.reindex_all()} chunks",
        None,
        gradio('kb_status'),
        show_progress=False,
    )

    shared.gradio['kb_search'].click(
        lambda q: ("✅ Search completed", rag_engine.format_rag_context(q, top_k=5)),
        gradio('kb_query'),
        gradio('kb_status', 'kb_results'),
        show_progress=False,
    )
