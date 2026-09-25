"""GTK workflow checks using disposable SSH files and UUID metadata."""
import copy
import gi

gi.require_foreign("cairo")
import cairo
import json
import os
import tempfile
import time
from pathlib import Path
from uuid import UUID
from unittest.mock import patch
from types import SimpleNamespace

with tempfile.TemporaryDirectory(prefix="confissh-ui-") as directory:
    os.environ["XDG_CONFIG_HOME"] = directory
    os.environ.setdefault("NO_AT_BRIDGE", "1")
    os.environ["CONFISSH_LANGUAGE"] = "en"
    config = Path(directory) / "config"
    extra = Path(directory) / "extra.conf"
    extra.write_text("Host included\n HostName 192.0.2.5\n")
    config.write_text(f'Include "{extra}"\n\nHost github-work\n HostName github.com\n User git\n\n'
                      "Host prod-api\n HostName 192.0.2.12\n\n# Host archived\n# HostName 192.0.2.99\n")
    os.environ["CONFISSH_CONFIG"] = str(config)
    from confissh.app import ConfiSSHApplication, EntryDialog, KeysDialog, SettingsDialog, Gtk, Gdk, GLib, UNGROUPED_GROUP
    from confissh.storage import MetadataStore

    app = ConfiSSHApplication()
    app.set_application_id("io.github.confissh.ConfiSSH.uitest")
    app.register(None)
    app.activate()
    window = app.props.active_window

    def drain():
        until = time.monotonic() + .25
        while time.monotonic() < until:
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(.01)

    def capture(widget, name):
        widget.present()
        drain()
        widget.check_resize()
        widget.size_allocate(widget.get_allocation())
        # Render the widget directly: some compositors return black for dialogs.
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, widget.get_allocated_width(), widget.get_allocated_height())
        widget.draw(cairo.Context(surface))
        surface.write_to_png(f"/tmp/confissh-{name}.png")

    drain()
    assert len(window.all_entries()) == 4
    assert window.ordered_groups() == []
    assert [row.group_name for row in window.group_list.get_children()] == [UNGROUPED_GROUP]
    assert window.selected_group is None
    assert len(window.filtered_entries()) == 4
    assert len(window.store.data["connections"]) == 4
    assert {item["name"] for item in window.store.data["environments"].values()} == {
        "Production", "Sandbox", "Development"
    }
    for entry in window.all_entries():
        UUID(entry.connection_id)
        assert entry.group_id is None
    settings = SettingsDialog(window)
    tabs = settings.get_content_area().get_children()[0]
    assert "Groups" not in [tabs.get_tab_label_text(tabs.get_nth_page(i)) for i in range(tabs.get_n_pages())]
    def name_group(name, group_id=None, color=None):
        def fill():
            for widget in Gtk.Window.list_toplevels():
                if isinstance(widget, Gtk.Dialog) and widget.get_title() in ("New group", "Edit group") and widget.get_visible():
                    field = next(child for child in widget.get_content_area().get_children() if isinstance(child, Gtk.Entry))
                    field.set_text(name)
                    if color is not None:
                        color_row = next(child for child in widget.get_content_area().get_children()
                                         if isinstance(child, Gtk.Box))
                        checkbox = next(child for child in color_row.get_children() if isinstance(child, Gtk.CheckButton))
                        picker = next(child for child in color_row.get_children() if isinstance(child, Gtk.ColorButton))
                        checkbox.set_active(bool(color))
                        if color:
                            rgba = Gdk.RGBA()
                            rgba.parse(color)
                            picker.set_rgba(rgba)
                    widget.response(Gtk.ResponseType.OK)
                    return False
            return True
        GLib.timeout_add(50, fill)
        window.edit_group_name(group_id)
        return next(key for key, group in window.store.data["groups"].items() if group["name"] == name)

    def delete_group(group_id, target=None):
        def fill():
            for widget in Gtk.Window.list_toplevels():
                if isinstance(widget, Gtk.Dialog) and widget.get_title() == "Delete group" and widget.get_visible():
                    combo = next(child for child in widget.get_content_area().get_children() if isinstance(child, Gtk.ComboBoxText))
                    combo.set_active_id(target or "")
                    widget.response(Gtk.ResponseType.OK)
                    return False
            return True
        GLib.timeout_add(50, fill)
        window.delete_group_dialog(group_id)
    settings.hide()
    original_ssh = config.read_bytes(), extra.read_bytes()
    def fill_empty_group():
        for widget in Gtk.Window.list_toplevels():
            if isinstance(widget, Gtk.Dialog) and widget.get_title() == "New group" and widget.get_visible():
                field = next(child for child in widget.get_content_area().get_children() if isinstance(child, Gtk.Entry))
                field.set_text("Empty group")
                widget.response(Gtk.ResponseType.OK)
                return False
        return True
    GLib.timeout_add(50, fill_empty_group)
    window.new_group_button.clicked()
    assert window.selected_group == "Empty group"
    assert window.empty_action.get_label() == "Add connection to group"
    empty_id = next(key for key, group in window.store.data["groups"].items() if group["name"] == "Empty group")
    assert empty_id in MetadataStore(window.store.path).data["groups"]
    assert original_ssh == (config.read_bytes(), extra.read_bytes())
    delete_group(empty_id)
    settings.show_all()
    group_id = name_group("Operations", color="#9145b5")
    UUID(group_id)
    assert window.store.data["groups"][group_id]["color"] == "#9145b5"
    second_group = name_group("Personal")
    assert window.ordered_groups() == ["Operations", "Personal"]
    assert window.group_list.get_children()[-1].group_name == UNGROUPED_GROUP
    assert "ungrouped" not in [row[1] for row in window.filter_selector.get_model()]
    pinned = window.group_list.get_children()[-1]
    assert not window.group_context_menu(pinned.drag_surface, SimpleNamespace(button=3))
    assert not window.move_group(UNGROUPED_GROUP, "Operations")
    assert not window.move_group("Operations", UNGROUPED_GROUP)
    assert not pinned.drag_surface.drag_source_get_target_list()
    assert "Personal" in [r.group_name for r in window.group_list.get_children()]
    settings.environment_name.set_text("Staging")
    settings.save_environment()
    env_id = settings.environment_list.get_active_id()
    UUID(env_id)
    assert len(window.store.data["environments"]) == 4
    production_id = next(key for key, item in window.store.data["environments"].items() if item["name"] == "Production")
    sandbox_id = next(key for key, item in window.store.data["environments"].items() if item["name"] == "Sandbox")
    settings.environment_list.set_active_id(production_id)
    color = Gdk.RGBA()
    color.parse("#123456")
    settings.environment_color.set_rgba(color)
    settings.save_environment()
    settings.environment_list.set_active_id(sandbox_id)
    settings.delete_environment()
    settings.environment_list.set_active_id(env_id)
    before_restore = config.read_bytes(), extra.read_bytes()
    settings.restore_environments_button.clicked()
    assert window.store.data["environments"][production_id]["color"] == "#dc5454"
    assert {item["name"] for item in window.store.data["environments"].values()} == {
        "Production", "Sandbox", "Development", "Staging"
    }
    assert settings.environment_list.get_active_id() == env_id
    assert before_restore == (config.read_bytes(), extra.read_bytes())
    restored_environments = copy.deepcopy(window.store.data["environments"])
    settings.restore_environments_button.clicked()
    assert MetadataStore(window.store.path).data["environments"] == restored_environments

    host = window.doc.entries[0]
    connection_id = host.connection_id
    window.toggle_favorite(host)
    window.navigation.select_row(window.navigation.get_row_at_index(1))
    assert window.filtered_entries() == [host]
    window.navigation.select_row(window.navigation.get_row_at_index(0))
    window.search.set_text("5")
    assert window.query == "5"
    assert [row.entry.alias for row in window.host_list.get_children()] == ["included"]
    window.search.set_text("")
    assert len(window.host_list.get_children()) == 4
    editor = EntryDialog(window, host, [])
    entry_tabs = next(child for child in editor.get_content_area().get_children() if isinstance(child, Gtk.Notebook))
    assert [entry_tabs.get_tab_label_text(entry_tabs.get_nth_page(i))
            for i in range(entry_tabs.get_n_pages())] == ["Connection", "Organization", "Advanced", "Tunnels"]
    assert entry_tabs.get_current_page() == 0
    assert not editor.save_button.get_sensitive()
    for field in (*editor.fields.values(), *editor.setting_fields.values()):
        original = field.get_text()
        field.set_text("2222" if field is editor.fields["port"] else original + "changed")
        assert editor.save_button.get_sensitive()
        field.set_text(original)
        assert not editor.save_button.get_sensitive()
    editor.enabled.set_active(False)
    assert editor.save_button.get_sensitive()
    editor.enabled.set_active(True)
    assert not editor.save_button.get_sensitive()
    editor.extras.get_buffer().set_text("Compression yes")
    assert editor.save_button.get_sensitive()
    editor.extras.get_buffer().set_text("")
    assert not editor.save_button.get_sensitive()
    editor.group_selector.set_active_id(group_id)
    assert editor.save_button.get_sensitive()
    editor.group_selector.set_active_id("")
    assert not editor.save_button.get_sensitive()
    editor.environment_selector.set_active_id(env_id)
    assert editor.save_button.get_sensitive()
    editor.environment_selector.set_active_id("")
    assert not editor.save_button.get_sensitive()
    editor.add_tunnel("LocalForward", "1234 localhost:22")
    assert editor.save_button.get_sensitive()
    editor.tunnel_rows[-1][0].get_children()[-1].clicked()
    assert not editor.save_button.get_sensitive()
    for port in ("0", "65536", "9999999999"):
        editor.fields["port"].set_text(port)
        assert not editor.save_button.get_sensitive()
    editor.fields["port"].set_text("65535")
    assert editor.save_button.get_sensitive()
    editor.fields["port"].insert_text("x", 0)
    assert editor.fields["port"].get_text() == "65535"
    editor.fields["port"].set_text("")
    assert not editor.save_button.get_sensitive()
    key_folder = Path(directory) / "test keys"
    key_folder.mkdir()
    private_key = key_folder / "test identity"
    private_content = "-----BEGIN OPENSSH PRIVATE KEY-----\nTEST FIXTURE ONLY\n-----END OPENSSH PRIVATE KEY-----\n"
    private_key.write_text(private_content)
    public_key = key_folder / "test identity.pub"
    public_key.write_text("ssh-ed25519 AAAATEST fixture\n")
    # Real file chooser interaction, including a path containing spaces.
    def select_identity():
        for widget in Gtk.Window.list_toplevels():
            if isinstance(widget, Gtk.FileChooserDialog) and widget.get_visible():
                widget.set_filename(str(private_key))
                GLib.timeout_add(200, lambda: (widget.response(Gtk.ResponseType.OK), False)[1])
                return False
        return True
    GLib.timeout_add(50, select_identity)
    editor.identity_browse.clicked()
    from confissh.keys import identity_path
    assert identity_path(editor.fields["identityfile"].get_text()) == private_key
    assert editor.save_button.get_sensitive()
    editor.fields["identityfile"].set_text("")
    assert not editor.save_button.get_sensitive()
    with patch("confissh.app.Path.home", return_value=Path(directory)):
        key_dialog = KeysDialog(window)
        drain()
        assert key_dialog.status.get_text() == "No SSH keys found."
        key_dialog.roots = [key_folder]
        key_dialog.refresh()
        drain()
        assert len(key_dialog.key_list.get_children()) == 2
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        for path in (private_key, public_key):
            key_dialog.copy_key(path)
            assert clipboard.wait_for_text() == path.read_text()
            key_dialog.copy_key(path, path_only=True)
            assert clipboard.wait_for_text() == str(path)
        private_key.unlink()
        key_dialog.copy_key(private_key)
        assert key_dialog.status.get_text().startswith("Could not copy key:")
        clipboard.clear()
        key_dialog.destroy()
    for field in (editor.group_selector, editor.environment_selector, editor.fields["note"], editor.fields["tags"]):
        assert field.is_ancestor(entry_tabs.get_nth_page(1))
    for key in ("alias", "hostname", "user", "port", "identityfile", "proxyjump"):
        assert editor.fields[key].is_ancestor(entry_tabs.get_nth_page(0))
    assert editor.source_selector.is_ancestor(entry_tabs.get_nth_page(0))
    environment_choices = [row[0] for row in editor.environment_selector.get_model()]
    assert all(name in environment_choices for name in ("Production", "Sandbox", "Development", "Staging"))
    assert editor.environment_selector.get_active_id() == ""
    jump_choices = [row[0] for row in editor.proxyjump_selector.get_model()]
    assert "included" in jump_choices  # Include files are available too.
    assert "prod-api" in jump_choices
    assert host.alias not in jump_choices
    assert "archived" not in jump_choices
    editor.fields["proxyjump"].set_text("jump-user@outside.example:2222,bastion")
    assert editor.build_entry().get("proxyjump") == "jump-user@outside.example:2222,bastion"
    editor.proxyjump_selector.set_active_id("")
    assert editor.build_entry().get("proxyjump") == ""
    editor.proxyjump_selector.set_active_id("included")
    assert editor.build_entry().get("proxyjump") == "included"
    editor.group_selector.set_active_id(group_id)
    editor.environment_selector.set_active_id(env_id)
    editor.fields["tags"].set_text("rabbit, redis, mysql, REDIS")
    editor.fields["note"].set_text("Primary applications")
    editor.fields["alias"].set_text("github-renamed")
    editor.setting_fields["ConnectTimeout"].set_text("10")
    editor.add_tunnel("LocalForward", "15432 localhost:5432")
    edited = editor.build_entry()
    capture(editor, "editor")
    entry_tabs.set_current_page(1)
    capture(editor, "organization")
    editor.destroy()
    assert edited.connection_id == connection_id
    candidate = copy.deepcopy(window.doc)
    candidate.replace(candidate.entries[0], edited)
    real_preview = window.text_dialog
    def reject_save_preview(*args):
        raise AssertionError("Saving must not open a review dialog")
    window.text_dialog = reject_save_preview
    assert window.commit_candidate(candidate)
    before = config.read_bytes(), window.store.path.read_bytes()
    backups_before = window.store.list_backups()
    assert not window.commit_candidate(copy.deepcopy(window.doc))
    assert before == (config.read_bytes(), window.store.path.read_bytes())
    assert backups_before == window.store.list_backups()
    window.group_list.select_row(window.group_list.get_children()[-1])
    assert window.selected_group == UNGROUPED_GROUP
    assert window.page_title.get_text() == "Ungrouped connections"
    assert window.add_button.get_label() == "Add connection"
    assert connection_id not in [entry.connection_id for entry in window.filtered_entries()]
    assert len(window.filtered_entries()) == 3
    window.filter_selector.set_active_id("disabled")
    assert len(window.filtered_entries()) == 1
    window.filter_selector.set_active_id("all")
    window.navigation.select_row(window.navigation.get_row_at_index(0))
    window.text_dialog = lambda *args: True
    restore_point = sorted(window.store.backup_dir.glob("*.json"))[-1]
    record = window.store.data["connections"][connection_id]
    assert record["group_id"] == group_id
    assert record["environment_id"] == env_id
    assert record["favorite"]
    assert record["tags"] == ["rabbit", "redis", "mysql"]
    assert record["note"] == "Primary applications"
    assert "confissh:group" not in config.read_text()
    assert "rabbit" not in config.read_text()
    assert f"# confissh-key: {connection_id}" in config.read_text()
    assert "LocalForward 15432 localhost:5432" in config.read_text()
    assert "ProxyJump included" in config.read_text()
    reopened = EntryDialog(window, window.doc.entries[0], [])
    assert not reopened.save_button.get_sensitive()
    assert reopened.fields["proxyjump"].get_text() == "included"
    assert reopened.group_selector.get_active_id() == group_id
    assert reopened.environment_selector.get_active_id() == env_id
    assert reopened.fields["note"].get_text() == "Primary applications"
    assert reopened.fields["tags"].get_text() == "rabbit, redis, mysql"
    reopened.destroy()
    custom_jump = copy.deepcopy(window.doc.entries[0])
    next(option for option in custom_jump.options if option.key.lower() == "proxyjump").value = "user@outside.example:2222,bastion"
    reopened = EntryDialog(window, custom_jump, [])
    assert reopened.build_entry().get("proxyjump") == "user@outside.example:2222,bastion"
    reopened.destroy()

    unchanged = config.read_bytes(), extra.read_bytes()
    assert name_group("Servers", group_id) == group_id
    assert window.store.data["groups"][group_id]["color"] == "#9145b5"
    assert window.store.data["connections"][connection_id]["group_id"] == group_id
    assert window.doc.entries[0].group == "Servers"
    settings.environment_name.set_text("Live")
    settings.save_environment()
    assert window.environment_name(env_id) == "Live"
    assert unchanged == (config.read_bytes(), extra.read_bytes())
    window.search.set_text("MYSQL")
    window.search_changed(window.search)
    assert len(window.filtered_entries()) == 1
    window.search.set_text("")
    window.search_changed(window.search)
    assert window.move_group("Personal", "Servers")
    window.rebuild_groups()
    assert window.ordered_groups()[:2] == ["Personal", "Servers"]
    assert window.move_group("Servers", "Personal")
    window.rebuild_groups()
    assert window.ordered_groups() == ["Servers", "Personal"]
    custom_order = copy.deepcopy(window.store.data["groups"])
    window.group_sort_items["name"].activate()
    assert window.ordered_groups() == ["Personal", "Servers"]
    assert window.store.data["groups"] == custom_order
    assert ConfiSSHApplication().preferences["group_sort"] == "name"
    window.group_sort_items["custom"].activate()
    assert window.ordered_groups() == ["Servers", "Personal"]
    assert ConfiSSHApplication().preferences["group_sort"] == "custom"
    assert window.move_group("Personal", "Servers")
    window.rebuild_groups()
    persisted = MetadataStore(window.store.path)
    assert persisted.data["groups"][second_group]["order"] < persisted.data["groups"][group_id]["order"]

    included_host = next(e for e in window.all_entries() if e.alias == "included")
    editor = EntryDialog(window, included_host, [])
    assert editor.source_selector.get_active_id() == str(extra)
    editor.fields["alias"].set_text("included-renamed")
    candidate = copy.deepcopy(window.owner(included_host))
    candidate.replace(candidate.entries[0], editor.build_entry())
    editor.destroy()
    main_before = config.read_bytes()
    assert window.commit_candidate(candidate)
    assert "Host included-renamed" in extra.read_text()
    assert main_before == config.read_bytes()

    # New group selection is ID-based; duplication gets an independent ID.
    dialog_values = []
    def fill_new():
        for widget in Gtk.Window.list_toplevels():
            if isinstance(widget, EntryDialog) and widget.get_visible():
                dialog_values.append(widget.group_selector.get_active_id())
                widget.fields["alias"].set_text("new-server")
                widget.fields["hostname"].set_text("192.0.2.44")
                widget.source_selector.set_active_id(str(extra))
                widget.response(Gtk.ResponseType.OK)
                return False
        return True
    window.selected_group = "Servers"
    window.refresh_hosts()
    GLib.timeout_add(50, fill_new)
    window.add_button.clicked()
    assert dialog_values == [group_id]
    assert "Host new-server" in extra.read_text()
    def cancel_duplicate():
        for widget in Gtk.Window.list_toplevels():
            if isinstance(widget, EntryDialog) and widget.get_visible():
                assert widget.save_button.get_sensitive()
                assert widget.connection_id != connection_id
                assert widget.group_selector.get_active_id() == group_id
                widget.response(Gtk.ResponseType.CANCEL)
                return False
        return True
    GLib.timeout_add(50, cancel_duplicate)
    window.duplicate_entry(window.doc.entries[0])
    delete_group(group_id, second_group)
    assert group_id not in window.store.data["groups"]
    assert window.store.data["connections"][connection_id]["group_id"] == second_group
    assert window.doc.entries[0].group == "Personal"
    delete_group(second_group)
    assert window.store.data["connections"][connection_id]["group_id"] is None
    assert [row.group_name for row in window.group_list.get_children()] == [UNGROUPED_GROUP]
    assert window.selected_group is None
    assert len(window.filtered_entries()) == len(window.all_entries())
    assert connection_id in [entry.connection_id for entry in window.filtered_entries()]

    # Paired restore recovers both config and metadata, then reload is stable.
    settings.refresh_backups()
    settings.backup_list.set_active_id(str(restore_point))
    settings.backup_restore_button.clicked()
    assert window.store.data["connections"][connection_id]["favorite"]
    assert window.store.data["connections"][connection_id]["tags"] == []
    assert window.doc.entries[0].alias == "github-work"
    window.reload()
    assert window.doc.entries[0].connection_id == connection_id
    window.navigation.select_row(window.navigation.get_row_at_index(1))
    assert window.filtered_entries()[0].connection_id == connection_id
    window.navigation.select_row(window.navigation.get_row_at_index(0))
    window.filter_selector.set_active_id("disabled")
    assert len(window.filtered_entries()) == 1
    window.filter_selector.set_active_id("all")
    # The virtual group disappears when its last connection is assigned, and
    # reappears when a connection loses its group; it never enters metadata.
    original_data = copy.deepcopy(window.store.data)
    lifecycle_data = copy.deepcopy(original_data)
    lifecycle_group = window.store.save_group(lifecycle_data, None, "Ungrouped connections")
    window.save_metadata(lifecycle_data)
    window.group_list.select_row(window.group_list.get_children()[-1])
    for entry in window.all_entries():
        assert window.move_connection(entry.connection_id, lifecycle_group)
    window.rebuild_groups()
    assert all(row.group_name != UNGROUPED_GROUP for row in window.group_list.get_children())
    assert window.selected_group is None
    assert window.move_connection(connection_id, None)
    window.rebuild_groups()
    pinned = window.group_list.get_children()[-1]
    assert pinned.group_name == UNGROUPED_GROUP
    window.group_list.select_row(pinned)
    assert [entry.connection_id for entry in window.filtered_entries()] == [connection_id]
    for mode in ("name", "custom"):
        window.set_group_sort(mode)
        assert window.group_list.get_children()[-1].group_name == UNGROUPED_GROUP
        assert window.selected_group == UNGROUPED_GROUP
    another = next(entry.connection_id for entry in window.all_entries() if entry.connection_id != connection_id)
    with patch("confissh.app.Gtk.drag_finish") as finish:
        window.group_drop(window.group_list.get_children()[-1].drag_surface, None, 0, 0,
                          SimpleNamespace(get_data=lambda: another.encode()), 1, 0)
        finish.assert_called_once_with(None, True, False, 0)
    drain()
    assert window.store.data["connections"][another]["group_id"] is None
    assert len(window.filtered_entries()) == 2
    window.save_metadata(original_data)
    window.navigation.select_row(window.navigation.get_row_at_index(0))
    window.search.set_text("no such host")
    window.search_changed(window.search)
    assert window.empty.get_visible()
    window.empty_clicked()
    assert not window.empty.get_visible()
    window.paned.set_position(300)
    drain()
    assert app.preferences["sidebar_width"] == 300
    window.toggle_sidebar()
    assert not window.sidebar.get_visible()
    window.toggle_sidebar()
    for theme in ("dark", "light", "system"):
        settings.theme_selector.set_active_id(theme)
        drain()
        assert ConfiSSHApplication().theme == theme
        if theme != "system":
            capture(window, theme)
    settings.language_selector.set_active_id("tr")
    assert app.preferences["language"] == "tr"
    assert json.loads(app.preferences_path.read_text())["language"] == "tr"
    assert settings.language_changed
    settings.language_selector.set_active_id("system")
    assert app.preferences["language"] == "system"
    capture(settings, "settings")
    backup_page = next(i for i in range(tabs.get_n_pages())
                       if tabs.get_tab_label_text(tabs.get_nth_page(i)) == "Backups")
    tabs.set_current_page(backup_page)
    settings.refresh_backups()
    capture(settings, "backups")
    def confirm_backup_delete(accepted, all_backups=False):
        def respond():
            for widget in Gtk.Window.list_toplevels():
                if isinstance(widget, Gtk.MessageDialog) and widget.get_visible():
                    widget.response(Gtk.ResponseType.OK if accepted else Gtk.ResponseType.CANCEL)
                    return False
            return True
        GLib.timeout_add(50, respond)
        button = settings.backup_delete_all_button if all_backups else settings.backup_delete_button
        button.clicked()
    before_delete = config.read_bytes(), extra.read_bytes(), window.store.path.read_bytes()
    paths = window.store.list_backups()
    confirm_backup_delete(False)
    assert window.store.list_backups() == paths
    confirm_backup_delete(False, True)
    assert window.store.list_backups() == paths
    confirm_backup_delete(True)
    assert len(window.store.list_backups()) == len(paths) - 1
    confirm_backup_delete(True, True)
    assert window.store.list_backups() == []
    assert not settings.backup_delete_all_button.get_sensitive()
    assert not settings.backup_restore_button.get_sensitive()
    assert before_delete == (config.read_bytes(), extra.read_bytes(), window.store.path.read_bytes())
    assert not any(key in app.preferences for key in ("favorites", "environments", "group_order", "recent"))
    window.text_dialog = real_preview
    settings.destroy()
    old_window = window
    window.group_list.select_row(window.group_list.get_children()[-1])
    assert window.selected_group == UNGROUPED_GROUP
    def switch_live_language():
        for widget in Gtk.Window.list_toplevels():
            if isinstance(widget, SettingsDialog) and widget.get_visible():
                widget.language_selector.set_active_id("tr")
                return False
        return True
    GLib.timeout_add(50, switch_live_language)
    window.open_settings()
    drain()
    window = app.props.active_window
    assert window is not old_window
    assert window.add_button.get_label() == "Bağlantı ekle"
    assert window.selected_group == UNGROUPED_GROUP
    assert window.page_title.get_text() == "Grupsuzlar"
    window.destroy()
    app.quit()
    print("PASS: UUIDs, independent groups/environments, favorites, paired restore, Include ownership, forms, filters and themes")
