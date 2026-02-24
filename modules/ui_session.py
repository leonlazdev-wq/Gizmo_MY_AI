import gradio as gr

from modules import shared, ui, utils
from modules.collab import create_session_share, join_session, list_collaborators
from modules.plugin_manager import disable_plugin, enable_plugin, install_plugin, list_plugins
from modules.sso import test_connection
from modules.devtests import run_full_suite, run_smoke_tests
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
                with gr.Accordion('Appearance', open=False):
                    shared.gradio['show_minimal_footer'] = gr.Checkbox(label='Show minimal footer', value=shared.settings.get('show_minimal_footer', True))
                    shared.gradio['display_density'] = gr.Dropdown(label='Display density', choices=['Compact', 'Comfortable', 'Spacious'], value=shared.settings.get('display_density', 'Comfortable'))

            with gr.Column():
                gr.Markdown("## Extensions & flags")
                shared.gradio['save_settings'] = gr.Button('Save extensions settings to user_data/settings.yaml', elem_classes='refresh-button', interactive=not mu)
                shared.gradio['reset_interface'] = gr.Button("Apply flags/extensions and restart", interactive=not mu)
                with gr.Row():
                    with gr.Column():
                        shared.gradio['extensions_menu'] = gr.CheckboxGroup(choices=utils.get_available_extensions(), value=shared.args.extensions, label="Available extensions", info='Note that some of these extensions may require manually installing Python requirements through the command: pip install -r extensions/extension_name/requirements.txt', elem_classes='checkboxgroup-table')

                    with gr.Column():
                        shared.gradio['bool_menu'] = gr.CheckboxGroup(choices=get_boolean_arguments(), value=get_boolean_arguments(active=True), label="Boolean command-line flags", elem_classes='checkboxgroup-table')

        with gr.Accordion('Integrations', open=False):
            # Visual mock: [x] Workflows [ ] Collaboration [ ] Marketplace
            shared.gradio['int_workflows'] = gr.Checkbox(label='Enable Workflows', value=shared.settings.get('int_workflows', False))
            shared.gradio['int_collab'] = gr.Checkbox(label='Enable Collaboration', value=shared.settings.get('int_collab', False))
            shared.gradio['int_marketplace'] = gr.Checkbox(label='Enable Marketplace', value=shared.settings.get('int_marketplace', False))
            shared.gradio['int_forms'] = gr.Checkbox(label='Enable Forms', value=shared.settings.get('int_forms', False))
            shared.gradio['int_analytics'] = gr.Checkbox(label='Enable Analytics', value=shared.settings.get('int_analytics', False))
            shared.gradio['int_sso'] = gr.Checkbox(label='Enable SSO/OAuth', value=shared.settings.get('int_sso', False))
            shared.gradio['int_devtests'] = gr.Checkbox(label='Enable Developer Tests', value=shared.settings.get('int_devtests', False))

            gr.Markdown('### Marketplace')
            shared.gradio['marketplace_search'] = gr.Textbox(label='Search plugins', placeholder='Search plugins...')
            shared.gradio['marketplace_path'] = gr.Textbox(label='Install plugin from path', placeholder='dev_tools/sample_plugin')
            with gr.Row():
                shared.gradio['marketplace_install_btn'] = gr.Button('Install')
                shared.gradio['marketplace_enable_btn'] = gr.Button('Enable')
                shared.gradio['marketplace_disable_btn'] = gr.Button('Disable')
            shared.gradio['marketplace_name'] = gr.Textbox(label='Plugin name', placeholder='sample_plugin')
            shared.gradio['marketplace_status'] = gr.Textbox(label='Marketplace status', interactive=False)
            shared.gradio['marketplace_list'] = gr.JSON(label='Plugins')

            gr.Markdown('### Collaboration')
            shared.gradio['collab_session_id'] = gr.Textbox(label='Session ID', value='default_session')
            shared.gradio['collab_user_id'] = gr.Textbox(label='User ID', value='owner')
            with gr.Row():
                shared.gradio['collab_invite_btn'] = gr.Button('Invite link')
                shared.gradio['collab_join_btn'] = gr.Button('Join')
            shared.gradio['collab_token'] = gr.Textbox(label='Invite token')
            shared.gradio['collab_status'] = gr.Textbox(label='Collaborators status', interactive=False)
            shared.gradio['collab_members'] = gr.JSON(label='Collaborators')

            gr.Markdown('### SSO / OAuth')
            shared.gradio['sso_provider'] = gr.Dropdown(label='Provider', choices=['Google', 'Microsoft', 'Okta'], value='Google')
            shared.gradio['sso_client_id'] = gr.Textbox(label='Client ID')
            shared.gradio['sso_client_secret'] = gr.Textbox(label='Client Secret', type='password')
            shared.gradio['sso_test_btn'] = gr.Button('Test Connection')
            shared.gradio['sso_status'] = gr.Textbox(label='SSO status', interactive=False)

            gr.Markdown('### Developer Tests')
            with gr.Row():
                shared.gradio['devtests_smoke_btn'] = gr.Button('Run Smoke Tests')
                shared.gradio['devtests_full_btn'] = gr.Button('Run Full Suite')
            shared.gradio['devtests_output'] = gr.Textbox(label='Test output', lines=12, interactive=False)

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

        # Integrations events
        shared.gradio['marketplace_install_btn'].click(
            lambda p: f"✅ Installed {install_plugin(p)}" if p else '❌ Provide path',
            gradio('marketplace_path'),
            gradio('marketplace_status'),
            show_progress=False,
        )
        shared.gradio['marketplace_enable_btn'].click(
            lambda n: (enable_plugin(n), f"✅ Enabled {n}")[1],
            gradio('marketplace_name'),
            gradio('marketplace_status'),
            show_progress=False,
        )
        shared.gradio['marketplace_disable_btn'].click(
            lambda n: (disable_plugin(n), f"✅ Disabled {n}")[1],
            gradio('marketplace_name'),
            gradio('marketplace_status'),
            show_progress=False,
        )
        shared.gradio['marketplace_search'].change(
            lambda _q: list_plugins(),
            gradio('marketplace_search'),
            gradio('marketplace_list'),
            show_progress=False,
        )

        shared.gradio['collab_invite_btn'].click(
            lambda sid: create_session_share(sid),
            gradio('collab_session_id'),
            gradio('collab_token'),
            show_progress=False,
        )
        shared.gradio['collab_join_btn'].click(
            lambda token, user: str(join_session(token, user)),
            gradio('collab_token', 'collab_user_id'),
            gradio('collab_status'),
            show_progress=False,
        ).then(
            lambda sid: list_collaborators(sid),
            gradio('collab_session_id'),
            gradio('collab_members'),
            show_progress=False,
        )

        shared.gradio['sso_test_btn'].click(
            lambda p, cid, sec: test_connection(p, cid, sec).get('message', 'error'),
            gradio('sso_provider', 'sso_client_id', 'sso_client_secret'),
            gradio('sso_status'),
            show_progress=False,
        )

        shared.gradio['devtests_smoke_btn'].click(
            lambda: run_smoke_tests().get('stdout', ''),
            None,
            gradio('devtests_output'),
            show_progress=False,
        )
        shared.gradio['devtests_full_btn'].click(
            lambda: run_full_suite().get('stdout', ''),
            None,
            gradio('devtests_output'),
            show_progress=False,
        )


        shared.gradio['display_density'].change(
            lambda d: d,
            gradio('display_density'),
            gradio('display_density'),
            js="""(density) => {
                document.body.classList.remove('density-compact','density-comfortable','density-spacious');
                const key = (density || 'Comfortable').toLowerCase();
                document.body.classList.add('density-' + key);
                return density;
            }""",
            show_progress=False,
        )

        shared.gradio['show_minimal_footer'].change(
            lambda x: x,
            gradio('show_minimal_footer'),
            gradio('show_minimal_footer'),
            js="""(show) => {
                const f = document.getElementById('minimal-footer');
                if (f) f.style.display = show ? 'block' : 'none';
                return show;
            }""",
            show_progress=False,
        )

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
