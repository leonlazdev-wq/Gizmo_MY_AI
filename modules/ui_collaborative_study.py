"""Gradio UI tab for Collaborative Study Mode."""

from __future__ import annotations

import gradio as gr

from modules import shared
from modules.collaborative_study import (
    create_room,
    get_room_info,
    get_scoreboard,
    get_session_summary,
    join_room,
    list_active_rooms,
    send_chat_message,
    share_flashcard_deck,
    start_quiz,
    submit_answer,
)
from modules.flashcard_generator import list_decks

# Session state (per-user in single-user mode)
_current_room_code: str = ""
_current_participant: str = "You"
_quiz_question_index: int = 0


def _format_chat(chat_history):
    if not chat_history:
        return "<p style='color:gray'>No messages yet.</p>"
    lines = []
    for msg in chat_history[-30:]:
        ts = msg.get("timestamp", "")[:16].replace("T", " ")
        sender = msg.get("sender", "?")
        text = msg.get("message", "")
        lines.append(
            f"<div style='margin:4px 0'>"
            f"<span style='color:#8ec8ff;font-weight:bold'>{sender}</span> "
            f"<span style='color:gray;font-size:.8em'>({ts})</span><br>"
            f"{text}"
            f"</div>"
        )
    return "\n".join(lines)


def _format_participants(participants):
    if not participants:
        return "No participants."
    return "👥 " + ", ".join(participants)


def _format_scoreboard(scores):
    if not scores:
        return "<p style='color:gray'>No scores yet.</p>"
    rows = sorted(scores.items(), key=lambda x: -x[1])
    lines = ["<table style='width:100%'>"]
    for i, (name, score) in enumerate(rows):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        lines.append(f"<tr><td>{medal}</td><td>{name}</td><td><b>{score}</b></td></tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _do_create_room(room_name, participant_name):
    global _current_room_code, _current_participant
    name = participant_name.strip() or "You"
    _current_participant = name
    code, err = create_room(room_name, creator=name)
    if err:
        return err, "", "", "", ""
    _current_room_code = code
    room, _ = get_room_info(code)
    participants_str = _format_participants(room.get("participants", []) if room else [])
    return (
        f"✅ Room created! Share code: **{code}**",
        code,
        participants_str,
        "",
        _format_chat([]),
    )


def _do_join_room(room_code, participant_name):
    global _current_room_code, _current_participant
    name = participant_name.strip() or "Guest"
    _current_participant = name
    code = room_code.strip().upper()
    room, err = join_room(code, participant=name)
    if err:
        return err, "", ""
    _current_room_code = code
    participants_str = _format_participants(room.get("participants", []))
    chat_html = _format_chat(room.get("chat", []))
    return f"✅ Joined room '{room.get('name', code)}'.", participants_str, chat_html


def _do_send_chat(message):
    global _current_room_code, _current_participant
    if not _current_room_code:
        return "<p style='color:red'>❌ Not in a room.</p>"
    chat, err = send_chat_message(_current_room_code, _current_participant, message)
    if err:
        return f"<p style='color:red'>{err}</p>"
    return _format_chat(chat)


def _do_start_quiz(topic, num_questions):
    global _current_room_code, _quiz_question_index
    if not _current_room_code:
        return "❌ Not in a room.", "", "", ""
    _quiz_question_index = 0
    quiz, err = start_quiz(_current_room_code, topic, int(num_questions))
    if err:
        return err, "", "", ""
    questions = quiz.get("questions", [])
    if not questions:
        return "⚠️ No questions generated.", "", "", ""
    q = questions[0]
    q_text = _format_question(q, 1, len(questions))
    options = list(q.get("options", {}).keys())
    return (
        f"✅ Quiz started: {topic} ({len(questions)} questions)",
        q_text,
        gr.update(choices=options, value=None),
        _format_scoreboard({}),
    )


def _format_question(q, idx, total):
    opts = "\n".join(f"  {k}) {v}" for k, v in q.get("options", {}).items())
    return f"**Q{idx}/{total}:** {q.get('question', '')}\n\n{opts}"


def _do_submit_answer(answer):
    global _current_room_code, _current_participant, _quiz_question_index
    if not _current_room_code:
        return "❌ Not in a room.", "", gr.update(), _format_scoreboard({})
    correct, feedback = submit_answer(
        _current_room_code, _current_participant, _quiz_question_index, answer
    )
    scores = get_scoreboard(_current_room_code)
    scoreboard_html = _format_scoreboard(scores)

    # Advance to next question
    room, _ = get_room_info(_current_room_code)
    if room:
        questions = room.get("quiz", {}).get("questions", []) if room.get("quiz") else []
        _quiz_question_index += 1
        if _quiz_question_index < len(questions):
            q = questions[_quiz_question_index]
            options = list(q.get("options", {}).keys())
            q_text = _format_question(q, _quiz_question_index + 1, len(questions))
            return feedback, q_text, gr.update(choices=options, value=None), scoreboard_html
        else:
            summary = get_session_summary(_current_room_code)
            return feedback, f"Quiz complete!\n\n{summary}", gr.update(choices=[], value=None), scoreboard_html

    return feedback, "", gr.update(), scoreboard_html


def _do_share_deck(deck_name):
    global _current_room_code
    if not _current_room_code:
        return "❌ Not in a room.", ""
    cards, err = share_flashcard_deck(_current_room_code, deck_name)
    if err:
        return err, ""
    if not cards:
        return "⚠️ No cards loaded.", ""
    preview = "\n".join(
        f"**Card {i+1}:** {c.get('front', '')}"
        for i, c in enumerate(cards[:5])
    )
    if len(cards) > 5:
        preview += f"\n…and {len(cards)-5} more cards"
    return f"✅ Shared deck '{deck_name}' ({len(cards)} cards).", preview


def _do_refresh_room():
    global _current_room_code
    if not _current_room_code:
        return "", "", _format_chat([])
    room, err = get_room_info(_current_room_code)
    if err:
        return err, "", _format_chat([])
    participants_str = _format_participants(room.get("participants", []))
    chat_html = _format_chat(room.get("chat", []))
    return f"Room: {room.get('name', _current_room_code)} ({_current_room_code})", participants_str, chat_html


def create_ui():
    with gr.Tab("👥 Collaborative Study", elem_id="collab-study-tab"):

        with gr.Accordion("🏠 Room Management", open=True):
            with gr.Row():
                shared.gradio['cs_room_name'] = gr.Textbox(
                    label="Room Name", placeholder="e.g. Biology Study Group", scale=3
                )
                shared.gradio['cs_participant_name'] = gr.Textbox(
                    label="Your Name", placeholder="Your name", scale=2, value="You"
                )
                shared.gradio['cs_create_btn'] = gr.Button("🏠 Create Room", scale=1)
            with gr.Row():
                shared.gradio['cs_join_code'] = gr.Textbox(
                    label="Room Code", placeholder="Enter 6-character code", scale=2
                )
                shared.gradio['cs_join_btn'] = gr.Button("🚪 Join Room", scale=1)
            shared.gradio['cs_room_status'] = gr.Markdown("Not in a room.")
            shared.gradio['cs_room_code_display'] = gr.Textbox(
                label="Room Code (share this)", interactive=False
            )
            shared.gradio['cs_participants'] = gr.Markdown("No participants.")
            shared.gradio['cs_refresh_btn'] = gr.Button("🔄 Refresh")

        with gr.Tabs():
            with gr.Tab("📝 Quiz Mode"):
                with gr.Row():
                    shared.gradio['cs_quiz_topic'] = gr.Textbox(
                        label="Quiz Topic", placeholder="e.g. Photosynthesis", scale=3
                    )
                    shared.gradio['cs_quiz_num_q'] = gr.Slider(
                        minimum=3, maximum=20, value=5, step=1, label="Questions", scale=1
                    )
                    shared.gradio['cs_start_quiz_btn'] = gr.Button("🚀 Start Quiz", scale=1)
                shared.gradio['cs_quiz_status'] = gr.Textbox(label="Status", interactive=False)
                shared.gradio['cs_question_display'] = gr.Markdown("")
                shared.gradio['cs_answer_radio'] = gr.Radio(label="Your Answer", choices=[])
                shared.gradio['cs_submit_answer_btn'] = gr.Button("✅ Submit Answer")
                shared.gradio['cs_answer_feedback'] = gr.Textbox(label="Feedback", interactive=False)
                shared.gradio['cs_scoreboard'] = gr.HTML("<p style='color:gray'>Scoreboard will appear here.</p>")

            with gr.Tab("🃏 Flashcards"):
                with gr.Row():
                    shared.gradio['cs_deck_selector'] = gr.Dropdown(
                        label="Select Deck", choices=list_decks(), scale=3
                    )
                    shared.gradio['cs_share_deck_btn'] = gr.Button("📤 Share Deck", scale=1)
                shared.gradio['cs_deck_status'] = gr.Textbox(label="Status", interactive=False)
                shared.gradio['cs_deck_preview'] = gr.Markdown("")

            with gr.Tab("💬 Chat"):
                shared.gradio['cs_chat_display'] = gr.HTML(
                    "<p style='color:gray'>Chat messages will appear here.</p>"
                )
                with gr.Row():
                    shared.gradio['cs_chat_input'] = gr.Textbox(
                        label="Message", placeholder="Type a message…", scale=4
                    )
                    shared.gradio['cs_send_btn'] = gr.Button("Send 📨", scale=1)


def create_event_handlers():
    shared.gradio['cs_create_btn'].click(
        _do_create_room,
        inputs=[
            shared.gradio['cs_room_name'],
            shared.gradio['cs_participant_name'],
        ],
        outputs=[
            shared.gradio['cs_room_status'],
            shared.gradio['cs_room_code_display'],
            shared.gradio['cs_participants'],
            shared.gradio['cs_quiz_status'],
            shared.gradio['cs_chat_display'],
        ],
        show_progress=True,
    )

    shared.gradio['cs_join_btn'].click(
        _do_join_room,
        inputs=[
            shared.gradio['cs_join_code'],
            shared.gradio['cs_participant_name'],
        ],
        outputs=[
            shared.gradio['cs_room_status'],
            shared.gradio['cs_participants'],
            shared.gradio['cs_chat_display'],
        ],
        show_progress=True,
    )

    shared.gradio['cs_send_btn'].click(
        _do_send_chat,
        inputs=[shared.gradio['cs_chat_input']],
        outputs=[shared.gradio['cs_chat_display']],
        show_progress=False,
    )

    shared.gradio['cs_start_quiz_btn'].click(
        _do_start_quiz,
        inputs=[
            shared.gradio['cs_quiz_topic'],
            shared.gradio['cs_quiz_num_q'],
        ],
        outputs=[
            shared.gradio['cs_quiz_status'],
            shared.gradio['cs_question_display'],
            shared.gradio['cs_answer_radio'],
            shared.gradio['cs_scoreboard'],
        ],
        show_progress=True,
    )

    shared.gradio['cs_submit_answer_btn'].click(
        _do_submit_answer,
        inputs=[shared.gradio['cs_answer_radio']],
        outputs=[
            shared.gradio['cs_answer_feedback'],
            shared.gradio['cs_question_display'],
            shared.gradio['cs_answer_radio'],
            shared.gradio['cs_scoreboard'],
        ],
        show_progress=False,
    )

    shared.gradio['cs_share_deck_btn'].click(
        _do_share_deck,
        inputs=[shared.gradio['cs_deck_selector']],
        outputs=[
            shared.gradio['cs_deck_status'],
            shared.gradio['cs_deck_preview'],
        ],
        show_progress=True,
    )

    shared.gradio['cs_refresh_btn'].click(
        _do_refresh_room,
        inputs=[],
        outputs=[
            shared.gradio['cs_room_status'],
            shared.gradio['cs_participants'],
            shared.gradio['cs_chat_display'],
        ],
        show_progress=False,
    )
