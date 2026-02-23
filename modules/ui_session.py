import gradio as gr

from modules import shared, ui, utils

from modules import plugin_manager
from modules import collab, auth, sso, devtests, ci_trigger
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


        with gr.Accordion('Marketplace', open=False):
            shared.gradio['plugin_search'] = gr.Textbox(label='Search plugins', placeholder='Search plugins...')
            shared.gradio['plugin_source_path'] = gr.Textbox(label='Local plugin path', placeholder='dev_tools/sample_plugin')
            with gr.Row():
                shared.gradio['plugin_install_btn'] = gr.Button('Install')
                shared.gradio['plugin_enable_btn'] = gr.Button('Enable')
                shared.gradio['plugin_disable_btn'] = gr.Button('Disable')
            shared.gradio['plugin_name'] = gr.Textbox(label='Plugin name')
            shared.gradio['plugin_list'] = gr.Textbox(label='Plugin list', lines=6)
            shared.gradio['plugin_status'] = gr.Textbox(label='Marketplace status', interactive=False)

        with gr.Accordion('Security: SSO / OAuth', open=False):
            shared.gradio['sso_provider'] = gr.Dropdown(label='Provider', choices=['Google', 'Microsoft', 'Okta'], value='Google')
            shared.gradio['sso_client_id'] = gr.Textbox(label='Client ID')
            shared.gradio['sso_client_secret'] = gr.Textbox(label='Client Secret', type='password')
            shared.gradio['sso_redirect_uri'] = gr.Textbox(label='Redirect URI', value=sso.get_redirect_uri(), interactive=False)
            shared.gradio['sso_test_btn'] = gr.Button('Test Connection')
            shared.gradio['sso_status'] = gr.Textbox(label='SSO status', interactive=False)

        with gr.Accordion('Developer: Automated Testing & CI', open=False):
            shared.gradio['dev_smoke_btn'] = gr.Button('Run Smoke Tests')
            shared.gradio['dev_full_btn'] = gr.Button('Run Full Suite')
            shared.gradio['dev_ci_endpoint'] = gr.Textbox(label='CI endpoint URL')
            shared.gradio['dev_ci_token'] = gr.Textbox(label='CI token', type='password')
            shared.gradio['dev_ci_btn'] = gr.Button('Trigger CI Build')
            shared.gradio['devtest_status'] = gr.Textbox(label='Test status', interactive=False)
            shared.gradio['devtest_log'] = gr.Textbox(label='Log output', lines=20, interactive=False)

        with gr.Accordion('Collaborators & RBAC', open=False):
            shared.gradio['collab_session_id'] = gr.Textbox(label='Session ID', value='default')
            shared.gradio['collab_user_id'] = gr.Textbox(label='User ID', value='local-user')
            with gr.Row():
                shared.gradio['collab_invite_btn'] = gr.Button('Invite link')
                shared.gradio['collab_join_token'] = gr.Textbox(label='Join token')
                shared.gradio['collab_join_btn'] = gr.Button('Join')
            shared.gradio['collab_role'] = gr.Dropdown(label='Role', choices=['Owner', 'Editor', 'Viewer'], value='Owner')
            with gr.Row():
                shared.gradio['perm_read'] = gr.Checkbox(label='Read', value=True)
                shared.gradio['perm_write'] = gr.Checkbox(label='Write', value=True)
                shared.gradio['perm_run'] = gr.Checkbox(label='Run workflows', value=True)
                shared.gradio['perm_manage'] = gr.Checkbox(label='Manage integrations', value=True)
            shared.gradio['collab_save_perm_btn'] = gr.Button('Save changes')
            shared.gradio['collab_status'] = gr.Textbox(label='Collaboration status', interactive=False)
            shared.gradio['collab_table'] = gr.Markdown('No collaborators yet.')

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


        shared.gradio['integrations_save_btn'].click(
            lambda w, c, m, o, d: _save_integrations(w, c, m, o, d),
            gradio('enable_workflows', 'enable_collab', 'enable_marketplace', 'enable_sso', 'enable_devtests'),
            gradio('integrations_status'),
            show_progress=False,
        )

        shared.gradio['plugin_install_btn'].click(
            lambda p: _install_plugin(p),
            gradio('plugin_source_path'),
            gradio('plugin_status'),
            show_progress=False,
        )
        shared.gradio['plugin_enable_btn'].click(lambda n: _enable_plugin(n), gradio('plugin_name'), gradio('plugin_status'), show_progress=False)
        shared.gradio['plugin_disable_btn'].click(lambda n: _disable_plugin(n), gradio('plugin_name'), gradio('plugin_status'), show_progress=False)
        shared.gradio['plugin_search'].change(lambda _: _list_plugins(), gradio('plugin_search'), gradio('plugin_list'), show_progress=False)

        shared.gradio['sso_test_btn'].click(
            lambda p, cid, sec: str(sso.run_sso_test(p, cid, sec)),
            gradio('sso_provider', 'sso_client_id', 'sso_client_secret'),
            gradio('sso_status'),
            show_progress=False,
        )

        shared.gradio['dev_smoke_btn'].click(lambda: _run_smoke(), [], gradio('devtest_status', 'devtest_log'), show_progress=False)
        shared.gradio['dev_full_btn'].click(lambda: _run_full(), [], gradio('devtest_status', 'devtest_log'), show_progress=False)
        shared.gradio['dev_ci_btn'].click(
            lambda e, t: str(ci_trigger.trigger_ci(e, t)),
            gradio('dev_ci_endpoint', 'dev_ci_token'),
            gradio('devtest_status'),
            show_progress=False,
        )

        shared.gradio['collab_invite_btn'].click(
            lambda sid, uid: _create_invite(sid, uid),
            gradio('collab_session_id', 'collab_user_id'),
            gradio('collab_status'),
            show_progress=False,
        )
        shared.gradio['collab_join_btn'].click(
            lambda tok, uid: _join_invite(tok, uid),
            gradio('collab_join_token', 'collab_user_id'),
            gradio('collab_status'),
            show_progress=False,
        )
        shared.gradio['collab_save_perm_btn'].click(
            lambda sid, uid, role, r, w, ru, m: _save_perms(sid, uid, role, r, w, ru, m),
            gradio('collab_session_id', 'collab_user_id', 'collab_role', 'perm_read', 'perm_write', 'perm_run', 'perm_manage'),
            gradio('collab_status', 'collab_table'),
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



def _save_integrations(enable_workflows, enable_collab, enable_marketplace, enable_sso, enable_devtests):
    shared.settings['enable_workflows'] = bool(enable_workflows)
    shared.settings['enable_collab'] = bool(enable_collab)
    shared.settings['enable_marketplace'] = bool(enable_marketplace)
    shared.settings['enable_sso'] = bool(enable_sso)
    shared.settings['enable_devtests'] = bool(enable_devtests)
    return '✅ Integration toggles saved (opt-in).'


def _list_plugins():
    return "\n".join([f"- {item['name']} | enabled={item['enabled']} | scopes={item['scopes']}" for item in plugin_manager.list_plugins()]) or 'No plugins.'


def _install_plugin(path):
    if not shared.settings.get('enable_marketplace', False):
        return '❌ Marketplace integration is disabled in Integrations.'
    try:
        name = plugin_manager.install_plugin(path)
        return f'✅ Installed plugin: {name}'
    except Exception as exc:
        return f'❌ Install failed: {exc}'


def _enable_plugin(name):
    if not shared.settings.get('enable_marketplace', False):
        return '❌ Marketplace integration is disabled in Integrations.'
    plugin_manager.enable_plugin(name)
    return f'✅ Enabled {name}'


def _disable_plugin(name):
    plugin_manager.disable_plugin(name)
    return f'✅ Disabled {name}'


def _run_smoke():
    if not shared.settings.get('enable_devtests', False):
        return '❌ Developer tests integration is disabled.', ''
    res = devtests.run_smoke_tests()
    return ('✅ Smoke tests passed' if res['ok'] == 'true' else '❌ Smoke tests failed', res['output'])


def _run_full():
    if not shared.settings.get('enable_devtests', False):
        return '❌ Developer tests integration is disabled.', ''
    res = devtests.run_full_suite()
    return ('✅ Full suite passed' if res['ok'] == 'true' else '❌ Full suite failed', res['output'])


def _create_invite(session_id, user_id):
    if not shared.settings.get('enable_collab', False):
        return '❌ Collaboration integration is disabled in Integrations.'
    token = collab.create_session_share(session_id, owner_id=user_id)
    return f'✅ Invite token: {token}'


def _join_invite(token, user_id):
    if not shared.settings.get('enable_collab', False):
        return '❌ Collaboration integration is disabled in Integrations.'
    try:
        data = collab.join_session(token, user_id)
        return f"✅ Joined session {data['session_id']} as {data['role']}"
    except Exception as exc:
        return f'❌ Join failed: {exc}'


def _save_perms(session_id, user_id, role, can_read, can_write, can_run, can_manage):
    auth.set_role_defaults(session_id, user_id, role)
    auth.set_permissions(session_id, user_id, {
        'can_read': can_read,
        'can_write': can_write,
        'can_run': can_run,
        'can_manage': can_manage,
        'view_analytics': role == 'Owner',
    })
    return '✅ Permissions saved.', collab.collaborators_table(session_id)
