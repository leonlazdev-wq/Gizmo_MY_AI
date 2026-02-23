import gradio as gr

from modules import shared, ui, utils
from modules.google_workspace_tools import add_image_to_slide, apply_slide_designer_prompt, write_text_to_doc
from modules.utils import gradio


def create_ui():
    mu = shared.args.multi_user
    with gr.Tab("Session", elem_id="session-tab"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("## Settings")
                shared.gradio['toggle_dark_mode'] = gr.Button('Toggle light/dark theme 💡', elem_classes='refresh-button')
                shared.gradio['show_two_notebook_columns'] = gr.Checkbox(label='Show two columns in the Notebook tab', value=shared.settings['show_two_notebook_columns'])
                shared.gradio['paste_to_attachment'] = gr.Checkbox(label='Turn long pasted text into attachments in the Chat tab', value=shared.settings['paste_to_attachment'], elem_id='paste_to_attachment')
                shared.gradio['include_past_attachments'] = gr.Checkbox(label='Include attachments/search results from previous messages in the chat prompt', value=shared.settings['include_past_attachments'])

                gr.Markdown("## Integrations (opt-in)")
                # Visual mock: [ ] Workflows [ ] Collaboration [ ] Marketplace [ ] SSO [ ] Devtests
                shared.gradio['enable_workflows'] = gr.Checkbox(label='Enable Workflows', value=shared.settings.get('enable_workflows', False))
                shared.gradio['enable_collab'] = gr.Checkbox(label='Enable Collaboration', value=shared.settings.get('enable_collab', False))
                shared.gradio['enable_marketplace'] = gr.Checkbox(label='Enable Marketplace', value=shared.settings.get('enable_marketplace', False))
                shared.gradio['enable_sso'] = gr.Checkbox(label='Enable SSO/OAuth', value=shared.settings.get('enable_sso', False))
                shared.gradio['enable_devtests'] = gr.Checkbox(label='Enable Developer Tests', value=shared.settings.get('enable_devtests', False))
                shared.gradio['integrations_save_btn'] = gr.Button('Save integration toggles', elem_classes='refresh-button')
                shared.gradio['integrations_status'] = gr.Textbox(label='Integration status', interactive=False)

            with gr.Column():
                gr.Markdown("## Extensions & flags")
                shared.gradio['save_settings'] = gr.Button('Save extensions settings to user_data/settings.yaml', elem_classes='refresh-button', interactive=not mu)
                shared.gradio['reset_interface'] = gr.Button("Apply flags/extensions and restart", interactive=not mu)
                with gr.Row():
                    with gr.Column():
                        shared.gradio['extensions_menu'] = gr.CheckboxGroup(choices=utils.get_available_extensions(), value=shared.args.extensions, label="Available extensions", info='Note that some of these extensions may require manually installing Python requirements through the command: pip install -r extensions/extension_name/requirements.txt', elem_classes='checkboxgroup-table')

                    with gr.Column():
                        shared.gradio['bool_menu'] = gr.CheckboxGroup(choices=get_boolean_arguments(), value=get_boolean_arguments(active=True), label="Boolean command-line flags", elem_classes='checkboxgroup-table')

        with gr.Row():
            with gr.Column():
                with gr.Accordion('🎓 Lesson Studio & Connectors (for students)', open=False):
                    gr.Markdown(
                        """Where to find this: **Session tab**.

Quick setup links: [Google Docs API](https://developers.google.com/docs/api/quickstart/python) · [Google Slides API](https://developers.google.com/slides/api/quickstart/python) · [Google Drive API](https://developers.google.com/drive/api/quickstart/python) · [Google Classroom API](https://developers.google.com/classroom) · [GitHub Tokens](https://github.com/settings/tokens)

1. Create a Google Cloud service account and enable Docs/Slides/Drive APIs.
2. Share your target Doc/Slides file with the service-account email.
3. Paste credentials JSON path + file IDs below.
4. Build a lesson request and paste it into Chat.
5. Use actions to write Docs text and redesign Slides from prompts.
"""
                    )

                    with gr.Row():
                        shared.gradio['session_lesson_topic'] = gr.Textbox(label='Lesson topic', placeholder='Photosynthesis / Fractions / History')
                        shared.gradio['session_lesson_level'] = gr.Dropdown(label='Student level', choices=['elementary', 'middle school', 'high school', 'college', 'mixed'], value='middle school')
                        shared.gradio['session_lesson_language'] = gr.Textbox(label='Language', value='auto')
                        shared.gradio['session_lesson_duration'] = gr.Slider(label='Duration (minutes)', minimum=5, maximum=45, step=1, value=12)

                    shared.gradio['session_lesson_goals'] = gr.Textbox(label='Learning goals (one per line)', lines=3)
                    with gr.Row():
                        shared.gradio['session_lesson_include_quiz'] = gr.Checkbox(label='Include quiz', value=True)
                        shared.gradio['session_lesson_include_visuals'] = gr.Checkbox(label='Include visuals', value=True)
                    shared.gradio['session_build_lesson'] = gr.Button('Build lesson request', elem_classes='refresh-button')
                    shared.gradio['session_lesson_status'] = gr.Textbox(label='Lesson status', interactive=False)
                    shared.gradio['session_lesson_payload'] = gr.Textbox(label='Lesson prompt to send to AI', lines=8, elem_classes=['add_scrollbar'])

                    gr.HTML("<div class='sidebar-vertical-separator'></div>")
                    shared.gradio['session_gworkspace_credentials'] = gr.Textbox(label='Service account credentials JSON path', placeholder='/content/drive/MyDrive/your-service-account.json')
                    shared.gradio['session_google_doc_id'] = gr.Textbox(label='Google Doc ID')
                    shared.gradio['session_google_doc_text'] = gr.Textbox(label='Text to write to Google Doc', lines=3)
                    shared.gradio['session_google_doc_write'] = gr.Button('Write to Google Doc', elem_classes='refresh-button')

                    shared.gradio['session_google_slides_id'] = gr.Textbox(label='Google Slides Presentation ID')
                    with gr.Row():
                        shared.gradio['session_google_slide_number'] = gr.Number(value=1, precision=0, minimum=1, label='Slide number')
                        shared.gradio['session_google_slide_image_query'] = gr.Textbox(label='Image query')
                    shared.gradio['session_google_slide_add_image'] = gr.Button('Add image to slide', elem_classes='refresh-button')

                    shared.gradio['session_slide_designer_prompt'] = gr.Textbox(label='Slide designer prompt', lines=3, placeholder='change background color to #1D3557, add image in top right, move text 120 px down')
                    shared.gradio['session_slide_designer_text'] = gr.Textbox(label='Text for text box', lines=2)
                    shared.gradio['session_slide_designer_apply'] = gr.Button('Apply smart slide design', elem_classes='refresh-button')
                    shared.gradio['session_workspace_status'] = gr.Markdown('')

        shared.gradio['theme_state'] = gr.Textbox(visible=False, value='dark' if shared.settings['dark_theme'] else 'light')
        if not mu:
            shared.gradio['save_settings'].click(
                ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
                handle_save_settings, gradio('interface_state', 'preset_menu', 'extensions_menu', 'show_controls', 'theme_state'), gradio('save_contents', 'save_filename', 'save_root', 'file_saver'), show_progress=False)

        shared.gradio['toggle_dark_mode'].click(
            lambda x: 'dark' if x == 'light' else 'light', gradio('theme_state'), gradio('theme_state')).then(
            None, None, None, js=f'() => {{{ui.dark_theme_js}; toggleDarkMode(); localStorage.setItem("theme", document.body.classList.contains("dark") ? "dark" : "light")}}')

        shared.gradio['show_two_notebook_columns'].change(
            handle_default_to_notebook_change,
            gradio('show_two_notebook_columns', 'textbox-default', 'output_textbox', 'prompt_menu-default', 'textbox-notebook', 'prompt_menu-notebook'),
            gradio('default-tab', 'notebook-tab', 'textbox-default', 'output_textbox', 'prompt_menu-default', 'textbox-notebook', 'prompt_menu-notebook')
        )

        shared.gradio['session_build_lesson'].click(
            build_lesson_request,
            gradio('session_lesson_topic', 'session_lesson_level', 'session_lesson_language', 'session_lesson_duration', 'session_lesson_goals', 'session_lesson_include_quiz', 'session_lesson_include_visuals'),
            gradio('session_lesson_status', 'session_lesson_payload'),
            show_progress=False)

        shared.gradio['session_google_doc_write'].click(
            run_session_google_doc,
            gradio('session_gworkspace_credentials', 'session_google_doc_id', 'session_google_doc_text'),
            gradio('session_workspace_status'),
            show_progress=False)

        shared.gradio['session_google_slide_add_image'].click(
            run_session_google_slide_image,
            gradio('session_gworkspace_credentials', 'session_google_slides_id', 'session_google_slide_number', 'session_google_slide_image_query'),
            gradio('session_workspace_status'),
            show_progress=False)

        shared.gradio['session_slide_designer_apply'].click(
            run_session_slide_designer,
            gradio('session_gworkspace_credentials', 'session_google_slides_id', 'session_google_slide_number', 'session_slide_designer_prompt', 'session_slide_designer_text', 'session_google_slide_image_query'),
            gradio('session_workspace_status'),
            show_progress=False)

        # Reset interface event
        if not mu:
            shared.gradio['reset_interface'].click(
                set_interface_arguments, gradio('extensions_menu', 'bool_menu'), None).then(
                None, None, None, js='() => {document.body.innerHTML=\'<h1 style="font-family:monospace;padding-top:20%;margin:0;height:100vh;color:lightgray;text-align:center;background:var(--body-background-fill)">Reloading...</h1>\'; setTimeout(function(){location.reload()},2500); return []}')


def handle_save_settings(state, preset, extensions, show_controls, theme):
    contents = ui.save_settings(state, preset, extensions, show_controls, theme, manual_save=True)
    return [
        contents,
        "settings.yaml",
        "user_data/",
        gr.update(visible=True)
    ]


def handle_default_to_notebook_change(show_two_columns, default_input, default_output, default_prompt, notebook_input, notebook_prompt):
    if show_two_columns:
        # Notebook to default
        return [
            gr.update(visible=True),
            gr.update(visible=False),
            notebook_input,
            "",
            gr.update(value=notebook_prompt, choices=utils.get_available_prompts()),
            gr.update(),
            gr.update(),
        ]
    else:
        # Default to notebook
        return [
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(),
            gr.update(),
            gr.update(),
            default_input,
            gr.update(value=default_prompt, choices=utils.get_available_prompts())
        ]


def set_interface_arguments(extensions, bool_active):
    shared.args.extensions = extensions

    bool_list = get_boolean_arguments()

    for k in bool_list:
        setattr(shared.args, k, False)
    for k in bool_active:
        setattr(shared.args, k, True)
        if k == 'api':
            shared.add_extension('openai', last=True)

    shared.need_restart = True


def get_boolean_arguments(active=False):
    cmd_list = vars(shared.args)
    bool_list = sorted([k for k in cmd_list if type(cmd_list[k]) is bool and k not in ui.list_model_elements()])
    bool_active = [k for k in bool_list if vars(shared.args)[k]]

    if active:
        return bool_active
    else:
        return bool_list


def build_lesson_request(topic, level, language, duration_min, goals, include_quiz, include_visuals):
    topic = (topic or '').strip()
    if not topic:
        return "❌ Enter a lesson topic first.", ""

    goals_list = [g.strip() for g in (goals or '').split("\n") if g.strip()]
    goals_text = "\n".join(f"- {g}" for g in goals_list) if goals_list else "- Explain key idea in simple language"

    request = (
        f"Create a {int(duration_min)}-minute lesson for {level} students.\n"
        f"Topic: {topic}\n"
        f"Language: {language or 'auto'}\n"
        f"Goals:\n{goals_text}\n"
        f"Include quiz: {'yes' if include_quiz else 'no'}\n"
        f"Include visuals: {'yes' if include_visuals else 'no'}\n\n"
        "Output strict JSON with keys: title, language, bullets, tts_audio_url, images, quiz, slide_export."
    )
    return "✅ Lesson request ready. Copy to chat.", request


def run_session_google_doc(credentials_path, document_id, text):
    if not credentials_path or not document_id:
        return "Add credentials path and Google Doc ID first."

    try:
        return write_text_to_doc(credentials_path.strip(), document_id.strip(), text)
    except Exception as exc:
        return f"Google Docs action failed: {exc}"


def run_session_google_slide_image(credentials_path, presentation_id, slide_number, image_query):
    if not credentials_path or not presentation_id:
        return "Add credentials path and Google Slides Presentation ID first."

    try:
        return add_image_to_slide(credentials_path.strip(), presentation_id.strip(), int(slide_number), image_query)
    except Exception as exc:
        return f"Google Slides image action failed: {exc}"


def run_session_slide_designer(credentials_path, presentation_id, slide_number, designer_prompt, slide_text, image_query):
    if not credentials_path or not presentation_id:
        return "Add credentials path and Google Slides Presentation ID first."

    try:
        return apply_slide_designer_prompt(credentials_path.strip(), presentation_id.strip(), int(slide_number), designer_prompt, slide_text, image_query)
    except Exception as exc:
        return f"Slide designer failed: {exc}"
