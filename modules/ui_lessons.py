import json
from datetime import datetime

import gradio as gr

from modules import shared
from modules.google_workspace_tools import add_image_to_slide, apply_slide_designer_prompt, write_text_to_doc
from modules.utils import gradio


def build_lesson_request(topic, level, language, duration_min, goals, include_quiz, include_visuals, include_flashcards):
 main
    topic = (topic or '').strip()
    if not topic:
        return "❌ Enter a lesson topic first.", ""

    goals_list = [g.strip() for g in (goals or '').split("\n") if g.strip()]
    goals_text = "\n".join(f"- {g}" for g in goals_list) if goals_list else "- Explain key idea in simple language"

    payload = {
        "title": f"{topic} lesson",
        "language": language or "auto",
        "bullets": [
            f"What is {topic}?",
            f"Why {topic} matters",
            f"One real-life example",
            "Quick recap"
        ],
        "tts_audio_url": "",
        "images": [] if not include_visuals else [{"thumb_url": "", "annotated_url": "", "source": ""}],
        "quiz": [] if not include_quiz else [{"q": f"What best defines {topic}?", "choices": ["Correct concept", "Wrong concept", "Not related"], "answer_index": 0}],
        "slide_export": [{"slide_title": f"{topic} overview", "slide_bullets": ["Definition", "Example", "Key takeaway"]}],
        "flashcards": [] if not include_flashcards else [{"front": f"Define {topic}", "back": f"Short definition of {topic}"}],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    request = (
        f"Create a {int(duration_min)}-minute lesson for {level} students.\n"
        f"Topic: {topic}\n"
        f"Language: {language or 'auto'}\n"
        f"Goals:\n{goals_text}\n"
        f"Include quiz: {'yes' if include_quiz else 'no'}\n"
        f"Include visuals: {'yes' if include_visuals else 'no'}\n"
        f"Include flashcards: {'yes' if include_flashcards else 'no'}\n\n"
        "Return strict JSON with keys: title, language, bullets, tts_audio_url, images, quiz, slide_export."
    )

    return "✅ Lesson request ready. Send this to chat.", request + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def run_google_doc(credentials_path, document_id, text):
    if not credentials_path or not document_id:
        return "Add credentials path and Google Doc ID first."

    try:
        return write_text_to_doc(credentials_path.strip(), document_id.strip(), text)
 main
 main
    except Exception as exc:
        return f"Google Docs action failed: {exc}"


def run_google_slide_image(credentials_path, presentation_id, slide_number, image_query):
    if not credentials_path or not presentation_id:
        return "Add credentials path and Google Slides Presentation ID first."

    try:
        return add_image_to_slide(credentials_path.strip(), presentation_id.strip(), int(slide_number), image_query)
 main
 main
    except Exception as exc:
        return f"Google Slides image action failed: {exc}"


def run_google_slide_designer(credentials_path, presentation_id, slide_number, designer_prompt, slide_text, image_query):
    if not credentials_path or not presentation_id:
        return "Add credentials path and Google Slides Presentation ID first."

    try:
        return apply_slide_designer_prompt(credentials_path.strip(), presentation_id.strip(), int(slide_number), designer_prompt, slide_text, image_query)
 main
 main
    except Exception as exc:
        return f"Slide designer failed: {exc}"


def create_ui():
    with gr.Tab("Lessons", elem_id="lessons-tab"):
        gr.Markdown("## 📚 Lessons Studio")
        gr.Markdown("Interactive learning tab with text, voice, visuals, quizzes, connector automations, and Google Workspace copilot actions.")

        shared.gradio['lesson_progress_state'] = gr.State([])

        with gr.Row():
            with gr.Column(scale=3, elem_classes=['lesson-panel']):
        gr.Markdown("Interactive learning tab with text, voice, visuals, quizzes, and Google Workspace copilot actions.")

        with gr.Row():
            with gr.Column(scale=3):
 main
                gr.Markdown("### Lesson Builder")
                shared.gradio['lesson_topic'] = gr.Textbox(label='Topic', placeholder='Atoms, Fractions, WW2, Photosynthesis...')
                with gr.Row():
                    shared.gradio['lesson_level'] = gr.Dropdown(label='Level', choices=['elementary', 'middle school', 'high school', 'college', 'mixed'], value='middle school')
                    shared.gradio['lesson_language'] = gr.Textbox(label='Language', value='auto', placeholder='auto / en / sv / sr')
                    shared.gradio['lesson_duration'] = gr.Slider(label='Minutes', minimum=5, maximum=45, step=1, value=12)

                shared.gradio['lesson_goals'] = gr.Textbox(label='Learning goals (one per line)', lines=3)
                with gr.Row():
                    shared.gradio['lesson_quiz'] = gr.Checkbox(label='Include quiz', value=True)
                    shared.gradio['lesson_visuals'] = gr.Checkbox(label='Include visuals', value=True)
                    shared.gradio['lesson_flashcards'] = gr.Checkbox(label='Include flashcards', value=True)
                with gr.Row():
                    shared.gradio['lesson_concise_mode'] = gr.Checkbox(label='⚡ Fast concise mode', value=True)
                    shared.gradio['lesson_include_summary'] = gr.Checkbox(label='Include short summary', value=True)
                    shared.gradio['lesson_bullet_count'] = gr.Slider(label='Max bullets', minimum=2, maximum=6, step=1, value=4)
 main

                shared.gradio['lesson_build_btn'] = gr.Button('Build lesson payload', variant='primary')
                shared.gradio['lesson_status'] = gr.Textbox(label='Status', interactive=False)
                shared.gradio['lesson_payload'] = gr.Textbox(label='Lesson output (copy to chat)', lines=14, elem_classes=['add_scrollbar'])

                with gr.Row():
                    shared.gradio['lesson_save_progress_btn'] = gr.Button('💾 Save progress')
                    shared.gradio['lesson_progress_status'] = gr.Textbox(label='Progress', interactive=False)
                shared.gradio['lesson_progress_list'] = gr.Textbox(label='Recent saved lessons', lines=4)

                with gr.Row():
                    shared.gradio['lesson_export_format'] = gr.Dropdown(label='Export format', choices=['markdown', 'json', 'text'], value='markdown')
                    shared.gradio['lesson_export_btn'] = gr.Button('⬇ Export file')
                shared.gradio['lesson_export_status'] = gr.Textbox(label='Export status', interactive=False)
                shared.gradio['lesson_export_file'] = gr.File(label='Download exported lesson', interactive=False)

            with gr.Column(scale=2, elem_classes=['lesson-panel']):
                gr.Markdown("### 🎙️ Voice + Visual Controls")
                with gr.Group(elem_classes=['lesson-card']):
                    with gr.Row():
                        shared.gradio['lesson_mic_btn'] = gr.Button('🎤 Dictate')
                        shared.gradio['lesson_speak_btn'] = gr.Button('🔊 Speak text', variant='primary')
                        shared.gradio['lesson_stop_speak_btn'] = gr.Button('⏹ Stop')
                    shared.gradio['lesson_voice_text'] = gr.Textbox(label='Text for speech / dictation', lines=6, elem_id='lesson-voice-text')
                    with gr.Row():
                        shared.gradio['lesson_voice_choice'] = gr.Dropdown(label='Voice preset', choices=['Friendly Robot (auto)', 'Google US English', 'Microsoft', 'Samantha', 'David', 'Zira'], value='Friendly Robot (auto)')
                        shared.gradio['lesson_voice_rate'] = gr.Slider(label='Rate', minimum=0.7, maximum=1.4, step=0.05, value=1.0)
                        shared.gradio['lesson_voice_pitch'] = gr.Slider(label='Pitch', minimum=0.7, maximum=1.5, step=0.05, value=1.05)
                    with gr.Row():
                        shared.gradio['lesson_voice_custom_name'] = gr.Textbox(label='Custom voice name', placeholder='e.g. Aria, Daniel, Google UK English Female')
                        shared.gradio['lesson_voice_lang'] = gr.Textbox(label='Language filter', value='en', placeholder='en, en-US, sv-SE...')
                    with gr.Row():
                        shared.gradio['lesson_voice_list_btn'] = gr.Button('📋 List available browser voices')
                    shared.gradio['lesson_voice_status'] = gr.Textbox(label='Voice status', interactive=False)
                    shared.gradio['lesson_voice_list'] = gr.Textbox(label='Available voices', lines=5, interactive=False, elem_classes=['add_scrollbar'])

                gr.Markdown("### Visual Prompt")
                shared.gradio['lesson_visual_prompt'] = gr.Textbox(label='Visual prompt', lines=4, placeholder='Draw an atom with labels: nucleus, proton, neutron, electron.')
                with gr.Row():
                    shared.gradio['lesson_visual_btn'] = gr.Button('🖼 Generate visual prompt')
                    shared.gradio['lesson_visual_auto_btn'] = gr.Button('✨ Auto visual from lesson output')
                shared.gradio['lesson_visual_status'] = gr.Textbox(label='Visual status', interactive=False)
                shared.gradio['lesson_visual_output'] = gr.Textbox(label='Visual instruction output', lines=6)

                gr.Markdown("### Connector Automation (beyond Google Docs/Slides)")
                shared.gradio['lesson_connector_service'] = gr.Dropdown(
                    label='Service',
                    choices=['google slides', 'google docs', 'github', 'google classroom', 'notion', 'slack', 'jira'],
                    value='google slides'
                )
                shared.gradio['lesson_connector_goal'] = gr.Textbox(label='What should AI automate?', lines=3, placeholder='Create assignment in Classroom and matching issue checklist in GitHub')
                shared.gradio['lesson_connector_prompt_btn'] = gr.Button('⚙ Build automation prompt')
                shared.gradio['lesson_connector_status'] = gr.Textbox(label='Connector status', interactive=False)
                shared.gradio['lesson_connector_output'] = gr.Textbox(label='Automation prompt output', lines=6)

            with gr.Column(scale=2):
                gr.Markdown("### Voice + Visual Controls")
                with gr.Row():
                    shared.gradio['lesson_mic_btn'] = gr.Button('🎤 Dictate')
                    shared.gradio['lesson_speak_btn'] = gr.Button('🔊 Speak text')
                    shared.gradio['lesson_stop_speak_btn'] = gr.Button('⏹ Stop')
                shared.gradio['lesson_voice_text'] = gr.Textbox(label='Text for speech / dictation', lines=6, elem_id='lesson-voice-text')
                with gr.Row():
                    shared.gradio['lesson_voice_choice'] = gr.Dropdown(label='Voice', choices=['Friendly Robot (auto)', 'Google US English', 'Microsoft', 'Samantha', 'David', 'Zira'], value='Friendly Robot (auto)')
                    shared.gradio['lesson_voice_rate'] = gr.Slider(label='Rate', minimum=0.7, maximum=1.4, step=0.05, value=1.0)
                    shared.gradio['lesson_voice_pitch'] = gr.Slider(label='Pitch', minimum=0.7, maximum=1.5, step=0.05, value=1.05)
                shared.gradio['lesson_voice_status'] = gr.Textbox(label='Voice status', interactive=False)

                gr.Markdown("### Visual Prompt")
                shared.gradio['lesson_visual_prompt'] = gr.Textbox(label='Visual prompt', lines=4, placeholder='Draw an atom with labels: nucleus, proton, neutron, electron.')
                shared.gradio['lesson_visual_btn'] = gr.Button('🖼 Generate visual prompt to send to AI')
                shared.gradio['lesson_visual_output'] = gr.Textbox(label='Visual instruction output', lines=6)

 main
        with gr.Accordion('🔗 Google Workspace & Connectors Copilot', open=False):
            gr.Markdown(
                "Setup docs: [Google Docs API](https://developers.google.com/docs/api/quickstart/python) · "
                "[Google Slides API](https://developers.google.com/slides/api/quickstart/python) · "
                "[Google Drive API](https://developers.google.com/drive/api/quickstart/python) · "
                "[Google Classroom API](https://developers.google.com/classroom) · "
                "[GitHub tokens](https://github.com/settings/tokens)"
            )
            gr.Markdown("Use prompt-driven actions: create slide text boxes, recolor background, place images, and move text." )
 main

            shared.gradio['lesson_credentials'] = gr.Textbox(label='Service account credentials JSON path', placeholder='/content/drive/MyDrive/your-service-account.json')
            with gr.Row():
                shared.gradio['lesson_doc_id'] = gr.Textbox(label='Google Doc ID')
                shared.gradio['lesson_doc_write_btn'] = gr.Button('Write to Google Doc')
            shared.gradio['lesson_doc_text'] = gr.Textbox(label='Text for Google Doc', lines=3)

            with gr.Row():
                shared.gradio['lesson_slides_id'] = gr.Textbox(label='Google Slides Presentation ID')
                shared.gradio['lesson_slide_number'] = gr.Number(value=1, precision=0, minimum=1, label='Slide #')
            shared.gradio['lesson_slide_image_query'] = gr.Textbox(label='Image query', placeholder='clean education illustration')
            with gr.Row():
                shared.gradio['lesson_slide_add_image_btn'] = gr.Button('Add image to slide')

            shared.gradio['lesson_slide_designer_prompt'] = gr.Textbox(label='Designer prompt', lines=3, placeholder='change background color to #1D3557, add image in top right, move text 120 px down')
            shared.gradio['lesson_slide_designer_text'] = gr.Textbox(label='Text to insert in slide textbox', lines=2)
            shared.gradio['lesson_slide_design_btn'] = gr.Button('Apply smart slide design', variant='primary')
            shared.gradio['lesson_workspace_status'] = gr.Markdown('')


def create_event_handlers():
    shared.gradio['lesson_build_btn'].click(
        build_lesson_request,
        gradio('lesson_topic', 'lesson_level', 'lesson_language', 'lesson_duration', 'lesson_goals', 'lesson_quiz', 'lesson_visuals', 'lesson_flashcards'),
 main
        gradio('lesson_status', 'lesson_payload'),
        show_progress=False)

    shared.gradio['lesson_visual_btn'].click(
        lambda x: ("✅ Manual visual prompt generated.", f"Create an annotated educational image for: {x}\nInclude arrows, labels, and short caption."),
        gradio('lesson_visual_prompt'),
        gradio('lesson_visual_status', 'lesson_visual_output'),
        show_progress=False)

    shared.gradio['lesson_visual_auto_btn'].click(
        generate_visual_instruction_from_lesson,
        gradio('lesson_payload'),
        gradio('lesson_visual_status', 'lesson_visual_output'),
        show_progress=False)

    shared.gradio['lesson_connector_prompt_btn'].click(
        build_connector_automation_prompt,
        gradio('lesson_connector_service', 'lesson_connector_goal', 'lesson_payload'),
        gradio('lesson_connector_status', 'lesson_connector_output'),
        show_progress=False)

    shared.gradio['lesson_save_progress_btn'].click(
        save_progress,
        gradio('lesson_progress_state', 'lesson_topic', 'lesson_payload'),
        gradio('lesson_progress_state', 'lesson_progress_status', 'lesson_progress_list'),
        show_progress=False)

    shared.gradio['lesson_export_btn'].click(
        export_lesson_file,
        gradio('lesson_payload', 'lesson_export_format'),
        gradio('lesson_export_status', 'lesson_export_file'),
        lambda x: f"Create an annotated educational image for: {x}\nInclude arrows, labels, and short caption.",
        gradio('lesson_visual_prompt'),
        gradio('lesson_visual_output'),
 main
        show_progress=False)

    shared.gradio['lesson_doc_write_btn'].click(
        run_google_doc,
        gradio('lesson_credentials', 'lesson_doc_id', 'lesson_doc_text'),
        gradio('lesson_workspace_status'),
        show_progress=False)

    shared.gradio['lesson_slide_add_image_btn'].click(
        run_google_slide_image,
        gradio('lesson_credentials', 'lesson_slides_id', 'lesson_slide_number', 'lesson_slide_image_query'),
        gradio('lesson_workspace_status'),
        show_progress=False)

    shared.gradio['lesson_slide_design_btn'].click(
        run_google_slide_designer,
        gradio('lesson_credentials', 'lesson_slides_id', 'lesson_slide_number', 'lesson_slide_designer_prompt', 'lesson_slide_designer_text', 'lesson_slide_image_query'),
        gradio('lesson_workspace_status'),
        show_progress=False)

    shared.gradio['lesson_mic_btn'].click(
        lambda: None,
        None,
 main
        gradio('lesson_voice_status'),
        js="""() => {
            const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!Ctor) return '❌ Speech recognition not supported in this browser.';
            const rec = new Ctor();
            rec.lang = 'en-US';
            rec.interimResults = false;
            rec.maxAlternatives = 1;
            rec.onresult = (e) => {
                const text = e.results[0][0].transcript;
                const box = document.querySelector('#lesson-voice-text textarea, #lesson-voice-text input');
                if (box) {
                    box.value = text;
                    box.dispatchEvent(new Event('input', {bubbles: true}));
                }
            };
            rec.start();
            return '🎤 Listening...';
        }""",
        show_progress=False)

    shared.gradio['lesson_speak_btn'].click(
        lambda text, voice_pref, rate, pitch, custom_voice, lang: '',
        gradio('lesson_voice_text', 'lesson_voice_choice', 'lesson_voice_rate', 'lesson_voice_pitch', 'lesson_voice_custom_name', 'lesson_voice_lang'),
        gradio('lesson_voice_status'),
        js="""(text, voicePref, rate, pitch, customVoice, langFilter) => {
        lambda: None,
        gradio('lesson_voice_text', 'lesson_voice_choice', 'lesson_voice_rate', 'lesson_voice_pitch'),
        gradio('lesson_voice_status'),
        js="""(text, voicePref, rate, pitch) => {
 main
            const clean = (text || '').trim();
            if (!clean) return '❌ Enter text first.';
            const synth = window.speechSynthesis;
            const voices = synth.getVoices();
            if (!voices || !voices.length) return '⚠️ No browser voices loaded yet. Click "List available browser voices" first.';
            const pref = (voicePref || '').toLowerCase();
            const custom = (customVoice || '').toLowerCase().trim();
            const lang = (langFilter || 'en').toLowerCase().trim();
            const findByName = (name) => voices.find(v => v.name.toLowerCase().includes(name));
            const findByLang = () => voices.find(v => v.lang.toLowerCase().startsWith(lang));
            const pick = (custom && findByName(custom))
                || (pref && findByName(pref))
                || findByLang()
                || voices[0];
            const pref = (voicePref || '').toLowerCase();
            const pick = voices.find(v => v.name.toLowerCase().includes(pref)) || voices.find(v => v.lang.toLowerCase().startsWith('en')) || voices[0];
 main
            synth.cancel();
            const u = new SpeechSynthesisUtterance(clean);
            if (pick) u.voice = pick;
            u.rate = Number(rate || 1);
            u.pitch = Number(pitch || 1.05);
            synth.speak(u);
            return '✅ Speaking: ' + (pick ? `${pick.name} (${pick.lang})` : 'default voice');
        }""",
        show_progress=False)

    shared.gradio['lesson_voice_list_btn'].click(
        lambda: ('', ''),
        [],
        gradio('lesson_voice_status', 'lesson_voice_list'),
        js="""() => {
            const synth = window.speechSynthesis;
            const voices = synth.getVoices();
            if (!voices || !voices.length) {
                return ['⚠️ Voice list is empty right now. Retry once browser loads voices.', ''];
            }
            const lines = voices
                .map((v, i) => `${i + 1}. ${v.name} | ${v.lang}${v.default ? ' | default' : ''}`)
                .join('\n');
            return [`✅ Loaded ${voices.length} browser voices.`, lines];
            return '✅ Speaking: ' + (pick ? pick.name : 'default voice');
 main
        }""",
        show_progress=False)

    shared.gradio['lesson_stop_speak_btn'].click(
        lambda: None,
        None,
 main
        gradio('lesson_voice_status'),
        js="() => { window.speechSynthesis.cancel(); return '⏹ Speech stopped.'; }",
        show_progress=False)
