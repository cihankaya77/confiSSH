from __future__ import annotations

import os
import json
import copy
import difflib
import time
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, Gtk, GLib  # noqa: E402

from . import __version__
from .storage import MetadataStore, new_id
from .i18n import _, ngettext, set_language, SUPPORTED_LANGUAGES
from .core import (
    PRIMARY_KEYS,
    ConfigDocument,
    ConfigError,
    ConfigOption,
    HostEntry,
    merge_options,
    parse_extra_options,
    included_paths,
    parse_tags,
)


APP_ID = "io.github.confissh.ConfiSSH"


def config_path() -> Path:
    override = os.environ.get("CONFISSH_CONFIG")
    return Path(override).expanduser() if override else Path.home() / ".ssh" / "config"


class HostRow(Gtk.ListBoxRow):
    def __init__(self, entry: HostEntry, app: "MainWindow"):
        super().__init__()
        self.entry = entry
        self.app = app
        self.get_style_context().add_class("host-row")
        self.set_selectable(False)
        self.set_activatable(False)
        self.set_can_focus(False)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        root.set_border_width(14)
        self.drag_surface = Gtk.EventBox()
        self.drag_surface.add(root)
        self.add(self.drag_surface)
        target = Gtk.TargetEntry.new("application/x-confissh-connection", Gtk.TargetFlags.SAME_APP, 1)
        self.drag_surface.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [target], Gdk.DragAction.MOVE)
        self.drag_surface.connect("drag-data-get", lambda _, context, selection, info, timestamp:
                                 selection.set(selection.get_target(), 8, entry.connection_id.encode("utf-8")))
        self.drag_surface.set_tooltip_text(_("Drag the connection to a group in the sidebar to move it."))

        status = Gtk.Label(label="●")
        status.get_style_context().add_class("status-on" if entry.enabled else "status-off")
        status.set_valign(Gtk.Align.START)
        root.pack_start(status, False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        root.pack_start(content, True, True, 0)

        title_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        alias = Gtk.Label(label=entry.alias, xalign=0)
        alias.set_ellipsize(3)
        alias.set_max_width_chars(30)
        alias.get_style_context().add_class("host-title")
        alias.set_tooltip_text(entry.alias)
        title_line.pack_start(alias, True, True, 0)
        badge = Gtk.Label(label=entry.group or _("Ungrouped"))
        badge.get_style_context().add_class("badge")
        apply_group_color(badge, app.store.data["groups"].get(entry.group_id, {}).get("color"))
        if entry.environment:
            environment = Gtk.Label(label=app.environment_name(entry.environment))
            environment.get_style_context().add_class("badge")
            color = app.store.data["environments"].get(entry.environment, {}).get("color", "#657b9e")
            rgba = Gdk.RGBA()
            if rgba.parse(color):
                provider = Gtk.CssProvider()
                provider.load_from_data((
                    f"label {{ color: {rgba.to_string()}; }}"
                    f".host-row {{ border-left-color: {rgba.to_string()}; }}"
                ).encode())
                environment.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
                self.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
            title_line.pack_start(environment, False, False, 0)
        if not entry.enabled:
            disabled = Gtk.Label(label=_("Disabled"))
            disabled.get_style_context().add_class("disabled-badge")
            title_line.pack_start(disabled, False, False, 0)
        content.pack_start(title_line, False, False, 0)
        # Environment stays next to the name; the group anchors the right edge.
        title_line.set_child_packing(alias, False, False, 0, Gtk.PackType.START)
        title_line.pack_start(Gtk.Box(), True, True, 0)
        if app.selected_group is None:
            title_line.pack_end(badge, False, False, 0)

        destination = entry.endpoint or _("No destination specified")
        user = entry.get("user") or _("user")
        port = entry.get("port") or "22"
        detail = Gtk.Label(label=f"{user}@{destination}:{port}", xalign=0)
        detail.get_style_context().add_class("host-detail")
        detail.set_ellipsize(3)
        detail.set_max_width_chars(32)
        detail.set_tooltip_text(detail.get_text())
        connection_line = Gtk.Box(spacing=10)
        connection_line.pack_start(detail, False, False, 0)
        content.pack_start(connection_line, False, False, 0)

        meta_parts = []
        if entry.get("identityfile"):
            meta_parts.append(_("Identity  {path}").format(path=entry.get("identityfile")))
        if entry.get("proxyjump"):
            meta_parts.append(_("Proxy  {host}").format(host=entry.get("proxyjump")))
        if entry.note:
            meta_parts.append(entry.note)
        if meta_parts:
            meta = Gtk.Label(label="   •   ".join(meta_parts), xalign=0)
            meta.set_ellipsize(3)
            meta.get_style_context().add_class("host-meta")
            content.pack_start(meta, False, False, 0)

        if entry.tags:
            tags = Gtk.FlowBox()
            tags.set_selection_mode(Gtk.SelectionMode.NONE)
            tags.set_can_focus(False)
            tags.set_min_children_per_line(min(3, len(entry.tags)))
            tags.set_max_children_per_line(6)
            tags.set_column_spacing(6)
            tags.set_row_spacing(4)
            tags.set_halign(Gtk.Align.START)
            tags.get_style_context().add_class("host-tags")
            for tag in entry.tags:
                label = Gtk.Label(label=tag)
                label.set_ellipsize(3)
                label.set_max_width_chars(16)
                label.set_tooltip_text(tag)
                label.get_style_context().add_class("tag")
                tags.add(label)
                label.get_parent().set_can_focus(False)
            connection_line.pack_start(tags, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        actions.set_valign(Gtk.Align.CENTER)
        root.pack_end(actions, False, False, 0)
        favorite = icon_button("starred-symbolic" if app.is_favorite(entry) else "non-starred-symbolic", _("Toggle favorite"))
        favorite.connect("clicked", lambda *_: app.toggle_favorite(entry))
        actions.pack_start(favorite, False, False, 0)
        copy_button = icon_button("edit-copy-symbolic", _("Copy SSH command"))
        copy_button.connect("clicked", lambda *_: app.copy_command(entry))
        actions.pack_start(copy_button, False, False, 0)
        edit_button = icon_button("document-edit-symbolic", _("Edit"))
        edit_button.connect("clicked", lambda *_: app.edit_entry(entry))
        actions.pack_start(edit_button, False, False, 0)
        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        menu_button.set_tooltip_text(_("More actions"))
        menu_button.get_style_context().add_class("flat")
        menu = Gtk.Menu()
        change_group = Gtk.MenuItem(label=_("Change group"))
        group_menu = Gtk.Menu()
        groups = [(None, _("Remove group assignment"))] + [
            (key, group["name"]) for key, group in sorted(
                app.store.data["groups"].items(), key=lambda item: item[1]["order"])
        ]
        for group_id, name in groups:
            item = Gtk.MenuItem(label=name)
            item.set_sensitive(group_id != entry.group_id)
            item.connect("activate", lambda _, target=group_id: self.change_group(target))
            group_menu.append(item)
        change_group.set_submenu(group_menu)
        menu.append(change_group)
        menu.append(Gtk.SeparatorMenuItem())
        source = Gtk.MenuItem(label=_("File: {name}").format(name=app.owner(entry).path.name))
        source.set_tooltip_text(str(app.owner(entry).path))
        source.set_sensitive(False)
        menu.append(source)
        for label, callback in ((_("Duplicate…"), app.duplicate_entry), (_("Effective configuration…"), app.effective_config)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _, fn=callback: fn(entry))
            menu.append(item)
        delete_item = Gtk.MenuItem(label=_("Delete connection…"))
        delete_item.connect("activate", lambda *_: app.delete_entry(entry))
        menu.append(delete_item)
        menu.show_all()
        menu_button.set_popup(menu)
        self.context_menu = menu
        self.drag_surface.connect("button-press-event", self.show_context_menu)
        actions.pack_start(menu_button, False, False, 0)
        connect_button = Gtk.Button(label=_("Connect"))
        connect_button.get_style_context().add_class("connect-button")
        connect_button.set_sensitive(entry.enabled)
        connect_button.connect("clicked", lambda *_: app.connect_to(entry))
        actions.pack_start(connect_button, False, False, 0)

    def show_context_menu(self, _widget, event):
        if event.button != 3:
            return False
        self.context_menu.popup_at_pointer(event)
        return True

    def change_group(self, group_id):
        if self.app.move_connection(self.entry.connection_id, group_id):
            self.app.rebuild_groups()


def apply_group_color(label, color):
    rgba = Gdk.RGBA()
    if color and rgba.parse(color):
        label.get_style_context().add_class("group-name")
        provider = Gtk.CssProvider()
        provider.load_from_data(f".group-name {{ color: {rgba.to_string()}; }}".encode())
        label.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)


def icon_button(icon: str, tooltip: str) -> Gtk.Button:
    button = Gtk.Button()
    button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
    button.set_tooltip_text(tooltip)
    button.get_style_context().add_class("flat")
    return button


class EntryDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, entry: HostEntry | None, groups: list[str]):
        title = _("Edit connection") if entry else _("New connection")
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(700, 710)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        save = self.add_button(_("Save"), Gtk.ResponseType.OK)
        save.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self.connection_id = entry.connection_id if entry else new_id()

        area = self.get_content_area()
        area.set_border_width(24)
        area.set_spacing(16)

        intro = Gtk.Label(
            label=_("SSH settings are under Connection; group, environment, tags, and note are under Organization."),
            xalign=0,
        )
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("muted")
        area.pack_start(intro, False, False, 0)
        notebook = Gtk.Notebook()
        area.pack_start(notebook, True, True, 0)

        connection_grid = Gtk.Grid(column_spacing=18, row_spacing=12)
        connection_grid.set_border_width(16)
        connection_scroll = Gtk.ScrolledWindow()
        connection_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        connection_scroll.add(connection_grid)
        notebook.append_page(connection_scroll, Gtk.Label(label=_("Connection")))
        organization_grid = Gtk.Grid(column_spacing=18, row_spacing=12)
        organization_grid.set_border_width(16)
        organization_scroll = Gtk.ScrolledWindow()
        organization_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        organization_scroll.add(organization_grid)
        notebook.append_page(organization_scroll, Gtk.Label(label=_("Organization")))
        self.fields: dict[str, Gtk.Entry] = {}
        values = {
            "alias": entry.alias if entry else "",
            "hostname": entry.get("hostname") if entry else "",
            "user": entry.get("user") if entry else "",
            "port": entry.get("port") if entry else "22",
            "identityfile": entry.get("identityfile") if entry else "",
            "proxyjump": entry.get("proxyjump") if entry else "",
            "group": entry.group if entry else (groups[0] if groups else ""),
            "note": entry.note if entry else "",
            "environment": entry.environment if entry else "",
            "tags": ", ".join(entry.tags) if entry else "",
        }
        connection_labels = (
            (_("Host alias"), "alias", _("for example, prod-api")),
            (_("Server / IP"), "hostname", _("for example, 192.0.2.12")),
            (_("User"), "user", _("for example, deploy")),
            ("Port", "port", "22"),
            ("IdentityFile", "identityfile", "~/.ssh/id_ed25519"),
            ("ProxyJump", "proxyjump", _("for example, bastion")),
        )
        organization_labels = (
            (_("Group"), "group", _("for example, Production")),
            (_("Environment"), "environment", "Production / Sandbox / Development"),
            (_("Tags"), "tags", _("rabbit, redis, mysql — separate with commas")),
            (_("Note"), "note", _("Short description")),
        )
        form_rows = [(connection_grid, row, label) for row, label in enumerate(connection_labels)]
        form_rows += [(organization_grid, row, label) for row, label in enumerate(organization_labels)]
        for grid, row, (label_text, key, placeholder) in form_rows:
            label = Gtk.Label(label=label_text, xalign=1)
            label.get_style_context().add_class("form-label")
            grid.attach(label, 0, row, 1, 1)
            if key == "group":
                self.group_selector = Gtk.ComboBoxText()
                self.group_selector.append("", _("Ungrouped"))
                for group_id, group in sorted(parent.store.data["groups"].items(), key=lambda item: item[1]["order"]):
                    self.group_selector.append(group_id, group["name"])
                self.group_selector.set_active_id(entry.group_id if entry and entry.group_id else "")
                grid.attach(self.group_selector, 1, row, 1, 1)
                continue
            if key == "environment":
                self.environment_selector = Gtk.ComboBoxText()
                self.environment_selector.append("", _("No environment selected"))
                environments = dict(parent.store.data["environments"])
                if entry and entry.environment:
                    environments.setdefault(entry.environment, "#637083")
                for environment in environments:
                    self.environment_selector.append(environment, parent.environment_name(environment))
                self.environment_selector.set_active_id(values[key])
                grid.attach(self.environment_selector, 1, row, 1, 1)
                continue
            if key == "proxyjump":
                self.proxyjump_selector = Gtk.ComboBoxText.new_with_entry()
                self.proxyjump_selector.append("", "")
                own_aliases = set(entry.aliases) if entry else set()
                aliases = {
                    alias
                    for host in parent.all_entries()
                    if host.enabled and host.connection_id != self.connection_id
                    for alias in host.aliases
                    if alias not in own_aliases and not any(char in alias for char in "*?![")
                }
                for alias in sorted(aliases, key=str.casefold):
                    self.proxyjump_selector.append(alias, alias)
                field = self.proxyjump_selector.get_child()
                self.proxyjump_selector.set_hexpand(True)
                self.proxyjump_selector.set_tooltip_text(
                    _("Select an SSH connection or enter a custom value (for example, bastion1,bastion2). "
                      "Leave it empty to disable ProxyJump.")
                )
                placeholder = _("Select a connection or enter a value")
                grid.attach(self.proxyjump_selector, 1, row, 1, 1)
            else:
                field = Gtk.Entry()
                grid.attach(field, 1, row, 1, 1)
            field.set_text(values[key])
            field.set_placeholder_text(placeholder)
            field.set_hexpand(True)
            if key == "alias":
                field.set_activates_default(True)
            self.fields[key] = field

        self.source_selector = Gtk.ComboBoxText()
        for path in parent.documents:
            self.source_selector.append(str(path), str(path))
        source = parent.owner(entry).path if entry and any(entry is item for item in parent.all_entries()) else parent.doc.path
        self.source_selector.set_active_id(str(source))
        self.source_selector.set_sensitive(entry is None)
        self.source_selector.set_tooltip_text(_("The destination file for a new connection. Existing connections are edited in their current file."))
        connection_grid.attach(Gtk.Label(label=_("Config file"), xalign=1), 0, len(connection_labels), 1, 1)
        connection_grid.attach(self.source_selector, 1, len(connection_labels), 1, 1)

        advanced_label = Gtk.Label(label=_("ADDITIONAL SSH SETTINGS"), xalign=0)
        advanced = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        advanced.set_border_width(16)
        notebook.append_page(advanced, Gtk.Label(label=_("Advanced")))
        advanced_label.get_style_context().add_class("section-label")
        advanced.pack_start(advanced_label, False, False, 0)
        hint = Gtk.Label(
            label=_("Type one directive per line. Start a line with # to keep it commented out."),
            xalign=0,
        )
        hint.get_style_context().add_class("muted")
        advanced.pack_start(hint, False, False, 0)

        self.setting_fields = {}
        for key, label in (("ConnectTimeout", _("Connection timeout (seconds)")),
                           ("ServerAliveInterval", _("Keep-alive interval (seconds)")),
                           ("ServerAliveCountMax", _("Unresponsive packet limit")),
                           ("IdentitiesOnly", _("Enable only specified identities (yes/no)"))):
            advanced.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
            field = Gtk.Entry()
            field.set_text(entry.get(key) if entry else "")
            self.setting_fields[key] = field
            advanced.pack_start(field, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.extras = Gtk.TextView()
        self.extras.set_monospace(True)
        self.extras.set_wrap_mode(Gtk.WrapMode.NONE)
        managed = {key.lower() for key in self.setting_fields} | {"localforward", "remoteforward"}
        extra_text = "\n".join(option.line(indent="") for option in entry.extra_options
                               if not option.enabled or option.key.lower() not in managed) if entry else ""
        self.extras.get_buffer().set_text(extra_text)
        scroll.add(self.extras)
        advanced.pack_start(scroll, True, True, 0)

        tunnels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tunnels.set_border_width(16)
        notebook.append_page(tunnels, Gtk.Label(label=_("Tunnels")))
        tunnels.pack_start(Gtk.Label(label=_("Listen: 127.0.0.1:5433   Target: localhost:5432"), xalign=0), False, False, 0)
        self.tunnel_rows = []
        self.tunnel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tunnel_scroll = Gtk.ScrolledWindow()
        tunnel_scroll.add(self.tunnel_box)
        tunnels.pack_start(tunnel_scroll, True, True, 0)
        add_tunnel = Gtk.Button(label=_("Add tunnel"))
        add_tunnel.connect("clicked", lambda *_: self.add_tunnel())
        tunnels.pack_start(add_tunnel, False, False, 0)
        if entry:
            for option in entry.options:
                if option.enabled and option.key.lower() in ("localforward", "remoteforward"):
                    self.add_tunnel(option.key, option.value)

        self.enabled = Gtk.Switch()
        self.enabled.set_active(entry.enabled if entry else True)
        enable_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        enable_row.pack_start(Gtk.Label(label=_("Connection active"), xalign=0), True, True, 0)
        enable_row.pack_end(self.enabled, False, False, 0)
        area.pack_start(enable_row, False, False, 0)
        self.show_all()

    def add_tunnel(self, kind="LocalForward", value=""):
        row = Gtk.Box(spacing=8)
        selector = Gtk.ComboBoxText()
        selector.append("LocalForward", _("Local → remote"))
        selector.append("RemoteForward", _("Remote → local"))
        selector.set_active_id("RemoteForward" if kind.lower() == "remoteforward" else "LocalForward")
        parts = value.split(None, 1)
        listen, target = Gtk.Entry(), Gtk.Entry()
        listen.set_placeholder_text("127.0.0.1:5433")
        target.set_placeholder_text("localhost:5432")
        listen.set_text(parts[0] if parts else "")
        target.set_text(parts[1] if len(parts) > 1 else "")
        record = (row, selector, listen, target)
        remove = icon_button("list-remove-symbolic", _("Remove tunnel"))
        def delete(*_args):
            self.tunnel_rows.remove(record)
            row.destroy()
        remove.connect("clicked", delete)
        for widget in (selector, listen, target, remove):
            row.pack_start(widget, widget in (listen, target), True, 0)
        self.tunnel_rows.append(record)
        self.tunnel_box.pack_start(row, False, False, 0)
        row.show_all()

    def build_entry(self) -> HostEntry:
        values = {key: field.get_text().strip() for key, field in self.fields.items()}
        buffer = self.extras.get_buffer()
        extra_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        extras = parse_extra_options(extra_text)
        for key, field in self.setting_fields.items():
            value = field.get_text().strip()
            if value:
                if key == "IdentitiesOnly":
                    if value not in ("yes", "no"):
                        raise ConfigError(_("IdentitiesOnly must be yes or no."))
                elif not value.isdigit():
                    raise ConfigError(_("{key} must be zero or a positive integer.").format(key=key))
                extras.append(ConfigOption(key, value))
        for _row, selector, listen, target in self.tunnel_rows:
            if not listen.get_text().strip() or not target.get_text().strip():
                raise ConfigError(_("Enter both the listen and target values for the tunnel."))
            extras.append(ConfigOption(selector.get_active_id(), listen.get_text().strip() + " " + target.get_text().strip()))
        option_values = {key: values[key] for key in PRIMARY_KEYS}
        return HostEntry(
            aliases=values["alias"].split(),
            options=merge_options(option_values, extras),
            group=self.group_selector.get_active_text() or "",
            group_id=self.group_selector.get_active_id() or None,
            connection_id=self.connection_id,
            note=values["note"],
            enabled=self.enabled.get_active(),
            environment=self.environment_selector.get_active_id() or "",
            tags=parse_tags(values["tags"]),
        )


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title=_("Settings"), transient_for=parent, modal=True)
        self.parent_window = parent
        self.app = parent.get_application()
        self.language_changed = False
        self.set_default_size(600, 560)
        self.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        tabs = Gtk.Notebook()
        tabs.set_scrollable(True)
        self.get_content_area().pack_start(tabs, True, True, 0)

        def page(title):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            box.set_border_width(24)
            tabs.append_page(box, Gtk.Label(label=title))
            return box

        appearance = page(_("Appearance"))
        appearance.pack_start(Gtk.Label(label=_("Theme"), xalign=0), False, False, 0)
        self.theme_selector = Gtk.ComboBoxText()
        for value, label in (("system", _("System default")), ("light", _("Light")), ("dark", _("Dark"))):
            self.theme_selector.append(value, label)
        self.theme_selector.set_active_id(self.app.theme)
        self.theme_selector.connect("changed", parent.change_theme)
        appearance.pack_start(self.theme_selector, False, False, 0)
        hint = Gtk.Label(label=_("Theme preference is saved automatically."), xalign=0)
        hint.get_style_context().add_class("muted")
        appearance.pack_start(hint, False, False, 0)

        appearance.pack_start(Gtk.Label(label=_("Language"), xalign=0), False, False, 6)
        self.language_selector = Gtk.ComboBoxText()
        for value, label in (("system", _("System default")), ("en", _("English")), ("tr", _("Turkish"))):
            self.language_selector.append(value, label)
        self.language_selector.set_active_id(self.app.language)
        self.language_selector.connect("changed", self.change_language)
        appearance.pack_start(self.language_selector, False, False, 0)
        language_hint = Gtk.Label(
            label=_("Changing the language refreshes the window immediately."), xalign=0)
        language_hint.get_style_context().add_class("muted")
        appearance.pack_start(language_hint, False, False, 0)
        self.language_message = Gtk.Label(xalign=0)
        self.language_message.set_line_wrap(True)
        appearance.pack_start(self.language_message, False, False, 0)

        shortcuts = page(_("Shortcuts"))
        shortcuts.pack_start(Gtk.Label(label=_("Keyboard shortcuts available in the main window."), xalign=0), False, False, 0)
        grid = Gtk.Grid(column_spacing=28, row_spacing=18)
        for row, (keys, description) in enumerate((
            ("Ctrl+F", _("Go to search")),
            ("Ctrl+N", _("Add a new connection")),
            ("Ctrl+R", _("Reload config files")),
            ("Esc", _("Clear search")),
        )):
            shortcut = Gtk.Label(label=keys, xalign=0)
            shortcut.get_style_context().add_class("badge")
            grid.attach(shortcut, 0, row, 1, 1)
            grid.attach(Gtk.Label(label=description, xalign=0), 1, row, 1, 1)
        shortcuts.pack_start(grid, False, False, 8)

        environments = page(_("Environments"))
        environments.pack_start(Gtk.Label(label=_("Define environments that can be assigned to connections."), xalign=0), False, False, 0)
        self.environment_list = Gtk.ComboBoxText()
        self.environment_list.connect("changed", self.select_environment)
        environments.pack_start(self.environment_list, False, False, 0)
        environments.pack_start(Gtk.Label(label=_("Environment name"), xalign=0), False, False, 0)
        self.environment_name = Gtk.Entry()
        self.environment_name.set_placeholder_text(_("For example: Production"))
        environments.pack_start(self.environment_name, False, False, 0)
        environments.pack_start(Gtk.Label(label=_("Badge color"), xalign=0), False, False, 0)
        self.environment_color = Gtk.ColorButton()
        self.environment_color.set_use_alpha(False)
        environments.pack_start(self.environment_color, False, False, 0)
        actions = Gtk.Box(spacing=8)
        save = Gtk.Button(label=_("Save environment"))
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self.save_environment)
        delete = Gtk.Button(label=_("Delete"))
        delete.connect("clicked", self.delete_environment)
        actions.pack_start(save, False, False, 0)
        actions.pack_start(delete, False, False, 0)
        self.restore_environments_button = Gtk.Button(label=_("Reset to defaults"))
        self.restore_environments_button.set_tooltip_text(
            _("Add missing Production, Sandbox, and Development environments and reset their colors. "
              "Custom or renamed environments and connection assignments are preserved.")
        )
        self.restore_environments_button.connect("clicked", self.restore_default_environments)
        actions.pack_end(self.restore_environments_button, False, False, 0)
        environments.pack_start(actions, False, False, 0)
        self.message = Gtk.Label(xalign=0)
        self.message.set_line_wrap(True)
        environments.pack_start(self.message, False, False, 0)
        self.refresh_environments()

        backups = page(_("Backups"))
        hint = Gtk.Label(label=_("SSH files and application data are backed up together. You can preview changes before restoring."), xalign=0)
        hint.set_line_wrap(True)
        backups.pack_start(hint, False, False, 0)
        self.backup_list = Gtk.ComboBoxText()
        backups.pack_start(self.backup_list, False, False, 0)
        backup_actions = Gtk.Box(spacing=8)
        self.backup_restore_button = Gtk.Button(label=_("Preview and restore"))
        self.backup_restore_button.connect("clicked", self.restore_backup)
        self.backup_delete_button = Gtk.Button(label=_("Delete selected…"))
        self.backup_delete_button.connect("clicked", lambda *_: self.delete_backups(False))
        self.backup_delete_all_button = Gtk.Button(label=_("Delete all…"))
        self.backup_delete_all_button.connect("clicked", lambda *_: self.delete_backups(True))
        for button in (self.backup_restore_button, self.backup_delete_button, self.backup_delete_all_button):
            backup_actions.pack_start(button, False, False, 0)
        backups.pack_start(backup_actions, False, False, 0)
        refresh = Gtk.Button(label=_("Refresh list"))
        refresh.set_halign(Gtk.Align.START)
        refresh.connect("clicked", lambda *_: self.refresh_backups())
        backups.pack_start(refresh, False, False, 0)
        self.backup_message = Gtk.Label(xalign=0)
        self.backup_message.set_line_wrap(True)
        backups.pack_start(self.backup_message, False, False, 0)
        self.refresh_backups()
        tabs.connect("switch-page", lambda _tabs, selected_page, _index:
                     self.refresh_backups() if selected_page is backups else None)

        files = page(_("Config files"))
        hint = Gtk.Label(label=_("Existing SSH connections are also available from Include files.\nYou can choose the destination file when adding a connection."), xalign=0)
        hint.set_line_wrap(True)
        files.pack_start(hint, False, False, 0)
        for path in [parent.store.path, *parent.documents]:
            label = Gtk.Label(label=str(path), xalign=0)
            label.set_selectable(True)
            label.set_ellipsize(2)
            label.set_tooltip_text(str(path))
            files.pack_start(label, False, False, 0)
        self.show_all()

    def change_language(self, selector):
        language = selector.get_active_id()
        if not language or language == self.app.language:
            return
        previous = self.app.language
        self.app.language = language
        self.app.preferences["language"] = language
        try:
            self.app.save_preferences()
        except OSError as exc:
            self.app.language = previous
            self.app.preferences["language"] = previous
            selector.set_active_id(previous)
            self.language_message.set_text(
                _("Language preference could not be saved: {error}").format(error=exc))
            return
        set_language(language)
        self.language_changed = True
        self.response(Gtk.ResponseType.APPLY)

    def refresh_backups(self):
        selected = self.backup_list.get_active_id()
        self.backup_list.remove_all()
        paths = self.parent_window.store.list_backups()
        for path in paths:
            self.backup_list.append(str(path), path.stem)
        if not selected or not self.backup_list.set_active_id(selected):
            self.backup_list.set_active(0)
        for button in (self.backup_restore_button, self.backup_delete_button, self.backup_delete_all_button):
            button.set_sensitive(bool(paths))
        self.backup_message.set_text(ngettext("{count} backup", "{count} backups", len(paths)).format(count=len(paths)) if paths else _("No backups yet."))

    def restore_backup(self, *_args):
        selected = self.backup_list.get_active_id()
        if not selected:
            return
        try:
            restored = self.parent_window.restore_snapshot(Path(selected), self)
        except (ConfigError, OSError, ValueError, KeyError, TypeError) as exc:
            self.backup_message.set_text(str(exc))
            return
        self.refresh_backups()
        if restored:
            self.refresh_environments()
            self.backup_message.set_text(_("Backup restored. A new backup was created for the previous state."))

    def delete_backups(self, all_backups=False):
        store = self.parent_window.store
        selected = self.backup_list.get_active_id()
        paths = store.list_backups() if all_backups else ([Path(selected)] if selected else [])
        if not paths:
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.CANCEL,
                                   text=_("Delete {count} backups permanently?").format(count=len(paths)) if all_backups else _("Delete the selected backup permanently?"))
        dialog.format_secondary_text(_("This operation cannot be undone. Current SSH files, connections, and application settings will not be deleted.")
                                     + ("" if all_backups else _("\nBackup: {name}").format(name=paths[0].stem)))
        dialog.add_button(_("Delete all") if all_backups else _("Delete backup"), Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if not accepted:
            return
        try:
            count = store.delete_backups(paths)
        except (ConfigError, OSError) as exc:
            self.refresh_backups()
            self.backup_message.set_text(str(exc))
            return
        self.refresh_backups()
        self.backup_message.set_text(ngettext("{count} backup was permanently deleted; it cannot be recovered.", "{count} backups were permanently deleted; they cannot be recovered.", count).format(count=count))

    def refresh_environments(self, selected="__new__"):
        self.environment_list.remove_all()
        self.environment_list.append("__new__", _("Create new environment"))
        for key in self.parent_window.store.data["environments"]:
            self.environment_list.append(key, self.parent_window.environment_name(key))
        self.environment_list.set_active_id(selected)

    def select_environment(self, selector):
        key = selector.get_active_id()
        if not key:
            return
        self.environment_name.set_text("" if key == "__new__" else self.parent_window.environment_name(key))
        rgba = Gdk.RGBA()
        rgba.parse(self.parent_window.store.data["environments"].get(key, {}).get("color", "#3568b0"))
        self.environment_color.set_rgba(rgba)

    def save_environment(self, *_args):
        name = self.environment_name.get_text().strip()
        key = self.environment_list.get_active_id()
        if not name or name == "__new__":
            self.message.set_text(_("Enter an environment name."))
            return
        others = [self.parent_window.environment_name(item).casefold()
                  for item in self.parent_window.store.data["environments"] if item != key]
        if name.casefold() in others:
            self.message.set_text(_("This environment name is already in use."))
            return
        if key == "__new__":
            key = new_id()
        data = copy.deepcopy(self.parent_window.store.data)
        data["environments"][key] = {"name": name, "color": self.environment_color.get_rgba().to_string()}
        try:
            self.parent_window.save_metadata(data)
        except (OSError, ConfigError) as exc:
            self.message.set_text(str(exc))
            return
        self.refresh_environments(key)
        self.parent_window.refresh_hosts()
        self.message.set_text(_("Environment saved."))

    def restore_default_environments(self, *_args):
        selected = self.environment_list.get_active_id() or "__new__"
        data = copy.deepcopy(self.parent_window.store.data)
        self.parent_window.store.restore_default_environments(data)
        try:
            self.parent_window.save_metadata(data)
        except (OSError, ConfigError) as exc:
            self.message.set_text(str(exc))
            return
        self.refresh_environments(selected)
        self.message.set_text(_("Default environments and colors were restored. Custom environments and connection assignments were preserved."))

    def delete_environment(self, *_args):
        key = self.environment_list.get_active_id()
        if not key or key == "__new__":
            return
        if any(record.get("environment_id") == key for record in self.parent_window.store.data["connections"].values()):
            self.message.set_text(_("The environment is in use. Change the environment of its connections first."))
            return
        data = copy.deepcopy(self.parent_window.store.data)
        data["environments"].pop(key, None)
        try:
            self.parent_window.save_metadata(data)
        except (OSError, ConfigError) as exc:
            self.message.set_text(str(exc))
            return
        self.refresh_environments()
        self.message.set_text(_("Environment was deleted."))



class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application):
        super().__init__(application=application, title="ConfiSSH")
        self.set_default_size(1160, 760)
        self.set_size_request(820, 560)
        self.documents = {path: ConfigDocument.load(path) for path in included_paths(config_path())}
        self.store = MetadataStore(application.preferences_path.with_name("connections.json"))
        self.store.synchronize(self.documents)
        self.doc = next(iter(self.documents.values()))
        self.selected_group = None
        self.favorites_view = False
        self.rebuilding_sidebar = False
        self.query = ""
        self.status_filter = "all"
        self.sort_order = "file"
        self.connect("key-press-event", self.keyboard_shortcut)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = "ConfiSSH"
        self.set_titlebar(header)

        open_button = icon_button("document-open-symbolic", _("Open config file"))
        open_button.connect("clicked", self.open_config)
        header.pack_start(open_button)
        reload_button = icon_button("view-refresh-symbolic", _("Reload"))
        reload_button.connect("clicked", self.reload)
        header.pack_start(reload_button)
        sidebar_button = icon_button("sidebar-show-symbolic", _("Show / hide sidebar"))
        sidebar_button.connect("clicked", lambda *_: self.toggle_sidebar())
        header.pack_start(sidebar_button)

        outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned = outer
        outer.set_wide_handle(False)
        self.add(outer)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.sidebar = sidebar
        sidebar.set_size_request(190, -1)
        sidebar.set_border_width(18)
        sidebar.get_style_context().add_class("sidebar")
        outer.pack1(sidebar, resize=False, shrink=False)

        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("network-server-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        brand.pack_start(icon, False, False, 0)
        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=_("Connections"), xalign=0)
        name.get_style_context().add_class("sidebar-title")
        brand_text.pack_start(name, False, False, 0)
        subtitle = Gtk.Label(label="ConfiSSH", xalign=0)
        subtitle.get_style_context().add_class("muted")
        brand_text.pack_start(subtitle, False, False, 0)
        brand.pack_start(brand_text, True, True, 0)
        sidebar.pack_start(brand, False, False, 5)

        self.navigation = Gtk.ListBox()
        self.navigation.get_style_context().add_class("group-list")
        self.navigation.connect("row-selected", self.navigation_selected)
        self.navigation_counts = {}
        for key, title, icon_name in (
            ("all", _("All connections"), "network-server-symbolic"),
            ("favorites", _("Favorites"), "starred-symbolic"),
        ):
            row = Gtk.ListBoxRow()
            row.view_name = key
            box = Gtk.Box(spacing=8)
            box.set_border_width(9)
            box.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU), False, False, 0)
            box.pack_start(Gtk.Label(label=title, xalign=0), True, True, 0)
            count = Gtk.Label()
            count.get_style_context().add_class("count")
            box.pack_end(count, False, False, 0)
            self.navigation_counts[key] = count
            row.add(box)
            self.navigation.add(row)
        sidebar.pack_start(self.navigation, False, False, 8)

        group_header = Gtk.Box(spacing=8)
        group_label = Gtk.Label(label=_("Groups"), xalign=0)
        group_label.get_style_context().add_class("section-label")
        group_header.pack_start(group_label, True, True, 0)
        self.new_group_button = icon_button("list-add-symbolic", _("New empty group"))
        self.new_group_button.connect("clicked", self.create_group)
        group_header.pack_end(self.new_group_button, False, False, 0)
        order_menu = Gtk.MenuButton()
        order_menu.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
        order_menu.get_style_context().add_class("flat")
        order_menu.set_tooltip_text(_("Group order"))
        menu = Gtk.Menu()
        self.group_sort_items = {}
        for mode, label in (("name", _("Alphabetical order")), ("custom", _("Custom order (drag and drop)"))):
            item = Gtk.CheckMenuItem(label=label)
            item.set_active(application.preferences.get("group_sort", "custom") == mode)
            item.connect("activate", lambda _, value=mode: self.set_group_sort(value))
            self.group_sort_items[mode] = item
            menu.append(item)
        menu.show_all()
        order_menu.set_popup(menu)
        group_header.pack_end(order_menu, False, False, 0)
        sidebar.pack_start(group_header, False, False, 4)
        self.group_list = Gtk.ListBox()
        self.group_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.group_list.get_style_context().add_class("group-list")
        self.group_list.connect("row-selected", self.group_selected)
        group_scroll = Gtk.ScrolledWindow()
        group_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        group_scroll.add(self.group_list)
        sidebar.pack_start(group_scroll, True, True, 0)

        settings_button = Gtk.Button(label=_("Settings"))
        settings_button.set_label("")
        settings_content = Gtk.Box(spacing=10)
        settings_content.set_halign(Gtk.Align.CENTER)
        settings_content.pack_start(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON), False, False, 0)
        settings_content.pack_start(Gtk.Label(label=_("Settings")), False, False, 0)
        settings_button.remove(settings_button.get_child())
        settings_button.add(settings_content)
        settings_button.set_margin_top(12)
        settings_button.set_margin_bottom(10)
        settings_button.set_margin_start(6)
        settings_button.set_margin_end(6)
        settings_button.connect("clicked", self.open_settings)
        sidebar.pack_start(settings_button, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main.set_border_width(24)
        outer.pack2(main, resize=True, shrink=False)
        outer.set_position(application.preferences.get("sidebar_width", 250))
        outer.connect("notify::position", self.remember_sidebar)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.page_title = Gtk.Label(label=_("All connections"), xalign=0)
        self.page_title.get_style_context().add_class("page-title")
        title_box.pack_start(self.page_title, False, False, 0)
        self.summary = Gtk.Label(xalign=0)
        self.summary.get_style_context().add_class("muted")
        title_box.pack_start(self.summary, False, False, 0)
        top.pack_start(title_box, True, True, 0)
        self.add_button = Gtk.Button(label=_("Add connection"))
        self.add_button.get_style_context().add_class("suggested-action")
        self.add_button.set_valign(Gtk.Align.CENTER)
        self.add_button.connect("clicked", lambda *_: self.edit_entry(None))
        top.pack_end(self.add_button, False, False, 0)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(_("Search by host, IP, user, or tag…"))
        self.search.set_width_chars(16)
        self.search.connect("changed", self.search_changed)
        main.pack_start(top, False, False, 0)

        toolbar = Gtk.Box(spacing=10)
        toolbar.pack_start(self.search, True, True, 0)
        self.filter_selector = Gtk.ComboBoxText()
        for value, label in (("all", _("All connections")), ("active", _("Active connections")), ("disabled", _("Disabled connections")), ("favorites", _("Favorites")), ("recent", _("Recent connections"))):
            self.filter_selector.append(value, label)
        self.filter_selector.set_active_id("all")
        self.filter_selector.connect("changed", self.change_filter)
        toolbar.pack_start(self.filter_selector, False, False, 0)
        self.sort_selector = Gtk.ComboBoxText()
        for value, label in (("file", _("File order")), ("name", _("Name · A–Z")), ("group", _("Sort by group"))):
            self.sort_selector.append(value, label)
        self.sort_selector.set_active_id("file")
        self.sort_selector.connect("changed", self.change_sort)
        toolbar.pack_end(self.sort_selector, False, False, 0)
        main.pack_start(toolbar, False, False, 0)

        self.info = Gtk.InfoBar()
        self.info.set_no_show_all(True)
        self.info.set_show_close_button(True)
        self.info_label = Gtk.Label(xalign=0)
        self.info_label.set_line_wrap(True)
        self.info.get_content_area().add(self.info_label)
        self.info.connect("response", lambda bar, *_: bar.hide())
        main.pack_start(self.info, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        self.list_scroll = scroll
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.host_list = Gtk.ListBox()
        self.host_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.host_list)
        main.pack_start(scroll, True, True, 0)

        self.empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.empty.set_valign(Gtk.Align.CENTER)
        empty_icon = Gtk.Image.new_from_icon_name("network-server-symbolic", Gtk.IconSize.DIALOG)
        self.empty.pack_start(empty_icon, False, False, 0)
        self.empty_title = Gtk.Label(label=_("No connection yet"))
        self.empty_title.get_style_context().add_class("empty-title")
        self.empty.pack_start(self.empty_title, False, False, 0)
        empty_hint = Gtk.Label(label=_("Start by adding a connection or clear the search filter."))
        self.empty_hint = empty_hint
        empty_hint.get_style_context().add_class("muted")
        self.empty.pack_start(empty_hint, False, False, 0)
        self.empty_action = Gtk.Button(label=_("Add connection"))
        self.empty_action.set_halign(Gtk.Align.CENTER)
        self.empty_action.get_style_context().add_class("suggested-action")
        self.empty_action.connect("clicked", self.empty_clicked)
        self.empty.pack_start(self.empty_action, False, False, 0)
        main.pack_start(self.empty, True, True, 0)

        self.rebuild_groups()
        self.refresh_hosts()
        self.show_all()
        self.info.hide()
        self.refresh_hosts()
        sidebar.set_visible(application.preferences.get("sidebar_visible", True))
        self.poll_source = GLib.timeout_add_seconds(2, self.check_external_change)
        self.connect("destroy", lambda *_: GLib.source_remove(self.poll_source))

    def remember_sidebar(self, *_args):
        self.get_application().preferences["sidebar_width"] = self.paned.get_position()
        self.get_application().save_preferences()

    def toggle_sidebar(self):
        visible = not self.sidebar.get_visible()
        self.sidebar.set_visible(visible)
        self.get_application().preferences["sidebar_visible"] = visible
        self.get_application().save_preferences()

    def check_external_change(self):
        try:
            if self.store.changed_on_disk() or any(document.changed_on_disk() for document in self.documents.values()):
                self.notify(_("The config changed outside the application. Reload with Ctrl+R before continuing."), True)
        except OSError as exc:
            self.notify(str(exc), True)
        return True

    def entry_key(self, entry):
        return entry.connection_id

    def is_favorite(self, entry):
        return self.store.data["connections"].get(entry.connection_id, {}).get("favorite", False)

    def save_metadata(self, data):
        self.store.commit(data, self.documents)
        self.rebuild_groups()

    def toggle_favorite(self, entry):
        data = copy.deepcopy(self.store.data)
        data["connections"][entry.connection_id]["favorite"] = not self.is_favorite(entry)
        try:
            self.save_metadata(data)
        except (ConfigError, OSError) as exc:
            self.error_dialog(str(exc))

    def ordered_groups(self):
        alphabetical = self.get_application().preferences.get("group_sort", "custom") == "name"
        groups = sorted(self.store.data["groups"].values(), key=lambda item:
                        (0 if alphabetical else item["order"], item["name"].casefold()))
        return [item["name"] for item in groups]

    def create_group(self, *_args):
        self.edit_group_name()

    def edit_group_name(self, group_id=None):
        if group_id is not None and group_id not in self.store.data["groups"]:
            return
        old_name = self.store.data["groups"].get(group_id, {}).get("name", "")
        dialog = Gtk.Dialog(title=_("Edit group") if group_id else _("New group"), transient_for=self, modal=True)
        dialog.set_default_size(360, 230)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Save") if group_id else _("Create group"), Gtk.ResponseType.OK).get_style_context().add_class("suggested-action")
        dialog.set_default_response(Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_border_width(20)
        area.set_spacing(10)
        area.pack_start(Gtk.Label(label=_("Group name") if group_id else _("You can add connections later."), xalign=0), False, False, 0)
        name = Gtk.Entry()
        name.set_text(old_name)
        name.set_placeholder_text(_("Group name"))
        name.set_activates_default(True)
        area.pack_start(name, False, False, 0)
        color_row = Gtk.Box(spacing=12)
        custom_color = Gtk.CheckButton(label=_("Custom color"))
        stored_color = self.store.data["groups"].get(group_id, {}).get("color")
        custom_color.set_active(bool(stored_color))
        color = Gtk.ColorButton()
        color.set_use_alpha(False)
        rgba = Gdk.RGBA()
        rgba.parse(stored_color or "#3568b0")
        color.set_rgba(rgba)
        color.set_sensitive(custom_color.get_active())
        custom_color.connect("toggled", lambda button: color.set_sensitive(button.get_active()))
        custom_color.set_tooltip_text(_("If disabled, the group name uses the theme color."))
        color_row.pack_start(custom_color, True, True, 0)
        color_row.pack_end(color, False, False, 0)
        area.pack_start(color_row, False, False, 0)
        error = Gtk.Label(xalign=0)
        error.set_line_wrap(True)
        area.pack_start(error, False, False, 0)
        dialog.show_all()
        name.grab_focus()
        name.select_region(0, -1)
        while dialog.run() == Gtk.ResponseType.OK:
            data = copy.deepcopy(self.store.data)
            try:
                rgba = color.get_rgba()
                hex_color = "#{:02x}{:02x}{:02x}".format(*(round(value * 255) for value in (rgba.red, rgba.green, rgba.blue)))
                key = self.store.save_group(data, group_id, name.get_text(), hex_color if custom_color.get_active() else "")
                self.store.commit(data, self.documents)
            except (ConfigError, OSError) as exc:
                error.set_text(str(exc))
                continue
            if group_id is None or self.selected_group == old_name:
                self.selected_group = data["groups"][key]["name"]
                self.favorites_view = False
            self.rebuild_groups()
            break
        dialog.destroy()

    def delete_group_dialog(self, group_id):
        if group_id not in self.store.data["groups"]:
            return
        name = self.store.data["groups"][group_id]["name"]
        dialog = Gtk.Dialog(title=_("Delete group"), transient_for=self, modal=True)
        dialog.set_default_size(420, 210)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Move and delete group"), Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        area = dialog.get_content_area()
        area.set_border_width(20)
        area.set_spacing(12)
        label = Gtk.Label(label=_("“{name}” will be deleted. Connections will not be deleted.\nSelect the group to move the connections to.").format(name=name), xalign=0)
        label.set_line_wrap(True)
        area.pack_start(label, False, False, 0)
        target = Gtk.ComboBoxText()
        target.append("", _("Ungrouped"))
        for key, item in self.store.data["groups"].items():
            if key != group_id:
                target.append(key, item["name"])
        target.set_active_id("")
        area.pack_start(target, False, False, 0)
        error = Gtk.Label(xalign=0)
        error.set_line_wrap(True)
        area.pack_start(error, False, False, 0)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            data = copy.deepcopy(self.store.data)
            try:
                self.store.delete_group(data, group_id, target.get_active_id() or None)
                self.save_metadata(data)
            except (OSError, ConfigError) as exc:
                error.set_text(str(exc))
                continue
            break
        dialog.destroy()

    def move_connection(self, connection_id, group_id):
        if connection_id not in {entry.connection_id for entry in self.all_entries()}:
            return False
        if group_id is not None and group_id not in self.store.data["groups"]:
            return False
        data = copy.deepcopy(self.store.data)
        data["connections"][connection_id]["group_id"] = group_id
        try:
            self.store.commit(data, self.documents)
        except (ConfigError, OSError) as exc:
            self.notify(_("Connection could not be moved: {error}").format(error=exc), True)
            return False
        group_name = data["groups"].get(group_id, {}).get("name", _("Ungrouped"))
        self.notify(_("Connection moved to “{group}”.").format(group=group_name))
        return True

    def move_group(self, source, target, after=False):
        groups = self.ordered_groups()
        if source not in groups or target not in groups or source == target:
            return False
        groups.remove(source)
        groups.insert(groups.index(target) + int(after), source)
        data = copy.deepcopy(self.store.data)
        for item in data["groups"].values():
            item["order"] = groups.index(item["name"])
        try:
            self.store.commit(data, self.documents)
        except (OSError, ConfigError) as exc:
            self.notify(_("Order could not be saved: {error}").format(error=exc), True)
            return False
        self.set_group_sort("custom", rebuild=False)
        return True

    def set_group_sort(self, mode, rebuild=True):
        if getattr(self, "updating_group_sort", False):
            return
        app = self.get_application()
        previous = app.preferences.get("group_sort", "custom")
        app.preferences["group_sort"] = mode
        try:
            app.save_preferences()
        except OSError as exc:
            app.preferences["group_sort"] = previous
            self.notify(_("Order preference could not be saved: {error}").format(error=exc), True)
        self.updating_group_sort = True
        for value, item in self.group_sort_items.items():
            item.set_active(value == app.preferences["group_sort"])
        self.updating_group_sort = False
        if rebuild:
            self.rebuild_groups()

    def group_drag_data(self, row, _context, selection, _info, _time):
        selection.set(selection.get_target(), 8, row.group_name.encode("utf-8"))

    def group_drop(self, row, context, _x, y, selection, info, timestamp):
        try:
            source = bytes(selection.get_data()).decode("utf-8")
        except (TypeError, UnicodeDecodeError):
            Gtk.drag_finish(context, False, False, timestamp)
            return
        if info == 1:
            success = self.move_connection(source, row.group_id)
        else:
            success = self.move_group(source, row.group_name,
                                      after=y >= row.get_allocated_height() / 2)
        Gtk.drag_finish(context, success, False, timestamp)
        if success:
            # Finish the drag before removing its source/destination widgets.
            GLib.idle_add(self.rebuild_groups)

    def group_context_menu(self, row, event):
        if event.button != 3:
            return False
        menu = Gtk.Menu()
        groups = self.ordered_groups()
        if row.group_name not in groups:
            return False
        key = next(key for key, group in self.store.data["groups"].items() if group["name"] == row.group_name)
        rename = Gtk.MenuItem(label=_("Rename…"))
        rename.connect("activate", lambda *_: self.edit_group_name(key))
        menu.append(rename)
        color_item = Gtk.MenuItem(label=_("Edit color…"))
        color_item.connect("activate", lambda *_: self.edit_group_name(key))
        menu.append(color_item)
        menu.append(Gtk.SeparatorMenuItem())
        index = groups.index(row.group_name)
        for label, offset in ((_("Move up"), -1), (_("Move down"), 1)):
            item = Gtk.MenuItem(label=label)
            target_index = index + offset
            item.set_sensitive(0 <= target_index < len(groups))
            if 0 <= target_index < len(groups):
                def move(_, target=groups[target_index], after=offset > 0):
                    if self.move_group(row.group_name, target, after):
                        self.rebuild_groups()
                item.connect("activate", move)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        delete = Gtk.MenuItem(label=_("Delete group…"))
        delete.connect("activate", lambda *_: self.delete_group_dialog(key))
        menu.append(delete)
        self.group_menu = menu
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def navigation_selected(self, _list, row):
        if row is None or self.rebuilding_sidebar:
            return
        self.favorites_view = row.view_name == "favorites"
        self.selected_group = None
        self.group_list.unselect_all()
        self.filter_selector.set_active_id("all")
        self.refresh_hosts()

    def duplicate_entry(self, entry):
        duplicate = copy.deepcopy(entry)
        duplicate.connection_id = new_id()
        duplicate.aliases = [entry.aliases[0] + "-copy"]
        self.edit_entry(None, template=duplicate)

    def open_settings(self, *_args):
        dialog = SettingsDialog(self)
        dialog.run()
        language_changed = dialog.language_changed
        dialog.destroy()
        if language_changed:
            GLib.idle_add(self.get_application().rebuild_window, self)

    def environment_name(self, key):
        return self.store.data["environments"].get(key, {}).get("name", key)

    def all_entries(self):
        return [entry for document in self.documents.values() for entry in document.entries]

    def owner(self, entry):
        return next((document for document in self.documents.values()
                     if any(item is entry for item in document.entries)), self.doc)

    def text_dialog(self, title, content, confirm=False, parent=None):
        dialog = Gtk.Dialog(title=title, transient_for=parent or self, modal=True)
        dialog.set_default_size(780, 560)
        dialog.add_button(_("Cancel") if confirm else _("Close"), Gtk.ResponseType.CANCEL)
        if confirm:
            dialog.add_button(_("Apply changes"), Gtk.ResponseType.OK)
        view = Gtk.TextView()
        view.set_monospace(True)
        view.set_editable(False)
        view.get_buffer().set_text(content)
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.show_all()
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        return accepted

    def commit_candidate(self, candidate):
        original = self.documents[candidate.path]
        diff = "".join(difflib.unified_diff(original.as_text().splitlines(True), candidate.as_text().splitlines(True), fromfile=str(original.path), tofile=_("Proposed changes")))
        data = copy.deepcopy(self.store.data)
        for entry in candidate.entries:
            data["connections"][entry.connection_id] = self.store.record(
                entry, data["connections"].get(entry.connection_id))
        # Keep records for removed hosts so externally removed/re-added keys retain metadata.
        metadata_diff = "".join(difflib.unified_diff(
            json.dumps(self.store.data, ensure_ascii=False, indent=2).splitlines(True),
            json.dumps(data, ensure_ascii=False, indent=2).splitlines(True),
            fromfile="connections.json", tofile=_("Proposed application data")))
        diff += "\n" + metadata_diff if metadata_diff else ""
        if not diff or not self.text_dialog(_("Review changes before saving"), diff, True):
            return False
        documents = {**self.documents, candidate.path: candidate}
        self.store.commit(data, documents)
        self.documents[candidate.path] = candidate
        if self.doc.path == candidate.path:
            self.doc = candidate
        self.rebuild_groups()
        self.refresh_hosts()
        self.notify(_("Changes were saved and the previous file was backed up."))
        return True

    def restore_snapshot(self, path, parent=None):
        snapshot = json.loads(path.read_text())
        self.store.validate(snapshot["metadata"])
        restored = copy.deepcopy(self.documents)
        for name, text in snapshot["documents"].items():
            source = Path(name)
            if source not in restored:
                raise ConfigError(_("A file from the backup is not in the current workspace: {name}").format(name=name))
            document = ConfigDocument(text or "", source)
            document.baseline = self.documents[source].baseline
            restored[source] = document
        staging = copy.copy(self.store)
        staging.data = snapshot["metadata"]
        data = staging.prepare(restored)
        preview = ""
        for source, document in restored.items():
            preview += "".join(difflib.unified_diff(self.documents[source].as_text().splitlines(True),
                                                  document.as_text().splitlines(True),
                                                  fromfile=str(source), tofile=_("Backup")))
        preview += _("\nApplication data:\n") + json.dumps(data, ensure_ascii=False, indent=2)
        if not self.text_dialog(_("Restore backup"), preview, True, parent):
            return False
        self.store.commit(data, restored)
        self.documents = restored
        self.doc = next(iter(restored.values()))
        self.rebuild_groups()
        self.notify(_("SSH files and application data were restored together."))
        return True

    def effective_config(self, entry):
        # OpenSSH evaluates Match exec during -G, so explicitly confirm execution.
        confirm = Gtk.MessageDialog(transient_for=self, modal=True, buttons=Gtk.ButtonsType.OK_CANCEL,
                                    text=_("Calculate the effective OpenSSH configuration?"))
        confirm.format_secondary_text(_("ssh -G does not connect, but it may run Match exec commands from the config."))
        accepted = confirm.run() == Gtk.ResponseType.OK
        confirm.destroy()
        if not accepted:
            return
        try:
            result = subprocess.run(["ssh", "-G", "-F", str(config_path()), "--", entry.aliases[0]], capture_output=True, text=True, timeout=10)
            self.text_dialog(_("Effective OpenSSH configuration"), result.stdout or result.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.error_dialog(str(exc))

    def change_theme(self, selector):
        try:
            self.get_application().set_theme(selector.get_active_id())
        except OSError as exc:
            self.notify(_("The theme was applied, but the preference could not be saved: {error}").format(error=exc), True)

    def change_filter(self, selector):
        self.status_filter = selector.get_active_id()
        self.refresh_hosts()

    def change_sort(self, selector):
        self.sort_order = selector.get_active_id()
        self.refresh_hosts()

    def empty_clicked(self, *_args):
        if not self.all_entries() or self.is_empty_group():
            self.edit_entry(None)
        else:
            self.search.set_text("")
            self.query = ""
            self.filter_selector.set_active_id("all")
            self.selected_group = None
            self.favorites_view = False
            self.rebuild_groups()

    def is_empty_group(self):
        return (self.selected_group is not None and not self.favorites_view
                and not any(entry.group == self.selected_group for entry in self.all_entries()))

    def keyboard_shortcut(self, _widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            key = Gdk.keyval_name(event.keyval).lower()
            if key == "f":
                self.search.grab_focus()
            elif key == "n":
                self.edit_entry(None)
            elif key == "r":
                self.reload()
            else:
                return False
            return True
        if event.keyval == Gdk.KEY_Escape:
            self.search.set_text("")
        return False

    @staticmethod
    def row_separator(row: Gtk.ListBoxRow, before: Gtk.ListBoxRow | None) -> None:
        row.set_header(Gtk.Separator()) if before else row.set_header(None)

    def rebuild_groups(self) -> None:
        self.rebuilding_sidebar = True
        for child in self.group_list.get_children():
            self.group_list.remove(child)
        entries = self.all_entries()
        groups = [(group, sum(e.group == group for e in entries)) for group in self.ordered_groups()]
        selected_row = None
        for group, count in groups:
            row = Gtk.ListBoxRow()
            row.group_name = group
            surface = Gtk.EventBox()
            surface.group_name = group
            surface.group_id = next((key for key, item in self.store.data["groups"].items()
                                     if item["name"] == group), None)
            row.drag_surface = surface
            row.set_tooltip_text(_("Drag connections onto this group. Drag the group to reorder it."))
            target = Gtk.TargetEntry.new("application/x-confissh-group", Gtk.TargetFlags.SAME_APP, 0)
            connection_target = Gtk.TargetEntry.new("application/x-confissh-connection", Gtk.TargetFlags.SAME_APP, 1)
            surface.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [target], Gdk.DragAction.MOVE)
            surface.drag_dest_set(Gtk.DestDefaults.ALL, [target, connection_target], Gdk.DragAction.MOVE)
            surface.connect("drag-data-get", self.group_drag_data)
            surface.connect("drag-data-received", self.group_drop)
            surface.connect("button-press-event", self.group_context_menu)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_border_width(9)
            grip = Gtk.Label(label="⠿")
            grip.get_style_context().add_class("muted")
            grip.set_tooltip_text(_("Drag to reorder the group"))
            box.pack_start(grip, False, False, 0)
            label = Gtk.Label(label=group, xalign=0)
            apply_group_color(label, self.store.data["groups"].get(surface.group_id, {}).get("color"))
            label.set_ellipsize(3)
            label.set_max_width_chars(21)
            label.set_tooltip_text(group)
            box.pack_start(label, True, True, 0)
            badge = Gtk.Label(label=str(count))
            badge.get_style_context().add_class("count")
            box.pack_end(badge, False, False, 0)
            surface.add(box)
            row.add(surface)
            self.group_list.add(row)
            if group == self.selected_group:
                selected_row = row
        self.group_list.show_all()
        if selected_row:
            self.navigation.unselect_all()
            self.group_list.select_row(selected_row)
        else:
            self.selected_group = None
            self.navigation.select_row(self.navigation.get_row_at_index(1 if self.favorites_view else 0))
        self.rebuilding_sidebar = False
        self.refresh_hosts()

    def filtered_entries(self) -> list[HostEntry]:
        query = self.query.casefold()
        entries = []
        for entry in self.all_entries():
            record = self.store.data["connections"].get(entry.connection_id, {})
            if self.favorites_view and not self.is_favorite(entry):
                continue
            if self.status_filter == "favorites" and not self.is_favorite(entry):
                continue
            if self.status_filter == "recent" and not record.get("last_used"):
                continue
            if self.status_filter == "active" and not entry.enabled:
                continue
            if self.status_filter == "disabled" and entry.enabled:
                continue
            if self.selected_group is not None and entry.group != self.selected_group:
                continue
            haystack = " ".join(
                [entry.alias, entry.group, self.environment_name(entry.environment), entry.endpoint, entry.get("user"), entry.note,
                 entry.get("identityfile"), entry.get("proxyjump"), *entry.tags]
            ).casefold()
            if query and query not in haystack:
                continue
            entries.append(entry)
        if self.sort_order == "name":
            entries.sort(key=lambda entry: entry.alias.casefold())
        elif self.sort_order == "group":
            entries.sort(key=lambda entry: (entry.group.casefold(), entry.alias.casefold()))
        if self.status_filter == "recent":
            entries.sort(key=lambda entry: self.store.data["connections"][entry.connection_id].get("last_used", 0), reverse=True)
        # Stable partition: retain the chosen order within each section.
        entries.sort(key=lambda entry: not self.is_favorite(entry))
        return entries

    def refresh_hosts(self) -> None:
        all_entries = self.all_entries()
        self.navigation_counts["all"].set_text(str(len(all_entries)))
        self.navigation_counts["favorites"].set_text(str(sum(self.is_favorite(e) for e in all_entries)))
        for child in self.host_list.get_children():
            self.host_list.remove(child)
        entries = self.filtered_entries()
        for entry in entries:
            self.host_list.add(HostRow(entry, self))
        self.host_list.show_all()
        self.host_list.set_visible(bool(entries))
        self.list_scroll.set_visible(bool(entries))
        self.empty.set_visible(not entries)
        self.empty_title.set_text(_("No results found") if self.all_entries() else _("Add your first connection"))
        self.empty_action.set_label(_("Clear filters") if self.all_entries() else _("Add connection"))
        if self.is_empty_group():
            self.empty_title.set_text(_("No connection in this group yet"))
            self.empty_hint.set_text(_("There is no connection in this group yet. Drag a connection here or add a new one."))
            self.empty_action.set_label(_("Add connection to group"))
        else:
            self.empty_hint.set_text(_("Start by adding a connection or clear the search filter."))
        active = sum(entry.enabled for entry in entries)
        self.summary.set_text(_("{count} connections  •  {active} active").format(count=len(entries), active=active))
        self.page_title.set_text(_("All connections") if self.selected_group is None else self.selected_group)
        if self.favorites_view:
            self.page_title.set_text(_("Favorites"))
        self.add_button.set_label(_("Add connection") if self.selected_group is None else _("Add connection to group"))

    def group_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None or self.rebuilding_sidebar:
            return
        self.favorites_view = False
        self.navigation.unselect_all()
        self.selected_group = row.group_name
        self.refresh_hosts()

    def search_changed(self, field: Gtk.SearchEntry) -> None:
        self.query = field.get_text().strip()
        self.refresh_hosts()

    def notify(self, message: str, error: bool = False) -> None:
        self.info.set_message_type(Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO)
        self.info_label.set_text(message)
        self.info.show_all()

    def edit_entry(self, entry: HostEntry | None, group=None, template=None) -> None:
        dialog = EntryDialog(self, template or entry, sorted({e.group for e in self.all_entries()}))
        dialog.source_selector.set_sensitive(entry is None)
        if not entry and not template:
            name = group or self.selected_group
            group_id = next((key for key, item in self.store.data["groups"].items() if item["name"] == name), "")
            dialog.group_selector.set_active_id(group_id)
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                new_entry = dialog.build_entry()
                source = self.owner(entry) if entry else self.documents[Path(dialog.source_selector.get_active_id())]
                candidate = copy.deepcopy(source)
                if entry:
                    old = next(e for e in candidate.entries if e.start == entry.start)
                    candidate.replace(old, new_entry)
                else:
                    candidate.add(new_entry)
                if not self.commit_candidate(candidate):
                    continue
                dialog.destroy()
                self.rebuild_groups()
                self.refresh_hosts()
                return
            except ConfigError as exc:
                self.error_dialog(str(exc), parent=dialog)
        dialog.destroy()

    def delete_entry(self, entry: HostEntry) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.CANCEL,
            text=_("Delete connection “{alias}”?").format(alias=entry.alias),
        )
        dialog.format_secondary_text(_("The config file will be backed up before this operation."))
        dialog.add_button(_("Delete connection"), Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                candidate = copy.deepcopy(self.owner(entry))
                candidate.delete(next(e for e in candidate.entries if e.start == entry.start))
                self.commit_candidate(candidate)
            except ConfigError as exc:
                self.error_dialog(str(exc))
        dialog.destroy()

    def copy_command(self, entry: HostEntry) -> None:
        command = shlex.join(["ssh", "-F", str(config_path()), "--", entry.aliases[0]])
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(command, -1)
        self.notify(_("Copied: {command}").format(command=command))

    def connect_to(self, entry: HostEntry) -> None:
        terminal = next(
            (binary for binary in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm") if shutil.which(binary)),
            None,
        )
        if not terminal:
            self.error_dialog(_("No terminal application was found. You can copy the SSH command instead."))
            return
        alias = entry.aliases[0]
        ssh_command = ["ssh", "-F", str(config_path()), "--", alias]
        command = [terminal, "-e", *ssh_command]
        if terminal.endswith("gnome-terminal"):
            command = [terminal, "--", *ssh_command]
        try:
            subprocess.Popen(command, start_new_session=True)
            data = copy.deepcopy(self.store.data)
            data["connections"][entry.connection_id]["last_used"] = time.time()
            self.save_metadata(data)
        except (OSError, ConfigError) as exc:
            self.error_dialog(_("Terminal could not be opened: {error}").format(error=exc))

    def open_config(self, *_args) -> None:
        path = self.doc.path
        if not path.exists():
            self.notify(_("The config file will be created when you save the first connection."))
            return
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)

    def reload(self, *_args) -> None:
        try:
            documents = {path: ConfigDocument.load(path) for path in included_paths(config_path())}
            store = MetadataStore(self.store.path)
            store.synchronize(documents)
            self.store = store
            self.documents = documents
            self.doc = next(iter(documents.values()))
            self.rebuild_groups()
            self.refresh_hosts()
            self.notify(_("Configuration files were reloaded from disk."))
        except ConfigError as exc:
            self.error_dialog(str(exc))

    def error_dialog(self, message: str, parent: Gtk.Window | None = None) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=parent or self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=_("Operation could not be completed"),
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()


class ConfiSSHApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.preferences_path = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "confissh" / "preferences.json"
        try:
            self.preferences = json.loads(self.preferences_path.read_text())
            if not isinstance(self.preferences, dict):
                self.preferences = {}
        except (OSError, ValueError, AttributeError):
            self.preferences = {}
        self.preferences = {key: value for key, value in self.preferences.items()
                            if key in ("theme", "sidebar_width", "sidebar_visible", "group_sort", "language")}
        if self.preferences.get("group_sort") not in ("name", "custom"):
            self.preferences["group_sort"] = "custom"
        self.language = self.preferences.get("language", "system")
        if self.language not in SUPPORTED_LANGUAGES:
            self.language = "system"
        set_language(os.environ.get("CONFISSH_LANGUAGE", self.language))
        self.theme = self.preferences.get("theme", "system")
        if self.theme not in ("light", "dark", "system"):
            self.theme = "system"

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.css = Gtk.CssProvider()
        self.settings = Gtk.Settings.get_default()
        self.system_dark = self.settings.get_property("gtk-application-prefer-dark-theme")
        self.desktop_settings = None
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.gnome.desktop.interface", True) if source else None
        if schema and schema.has_key("color-scheme"):
            self.desktop_settings = Gio.Settings.new("org.gnome.desktop.interface")
            self.desktop_settings.connect("changed::color-scheme", lambda *_: self.apply_theme())
        self.settings.connect("notify::gtk-theme-name", lambda *_: self.apply_theme())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.apply_theme()

        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self.show_about)
        self.add_action(about)

    def set_theme(self, theme):
        self.theme = theme
        self.apply_theme()
        self.preferences["theme"] = theme
        self.save_preferences()

    def save_preferences(self):
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.preferences_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.preferences), encoding="utf-8")
        temporary.replace(self.preferences_path)

    def apply_theme(self):
        desktop_scheme = self.desktop_settings.get_string("color-scheme") if self.desktop_settings else ""
        follows_dark = (
            desktop_scheme == "prefer-dark" if desktop_scheme else
            self.system_dark or "dark" in self.settings.get_property("gtk-theme-name").lower()
        )
        dark = self.theme == "dark" or (
            self.theme == "system" and follows_dark
        )
        self.settings.set_property("gtk-application-prefer-dark-theme", dark)
        colors = (
            ("#20242b", "#262b33", "#23272e", "#e7eaf0", "#a0acbc", "#363d47", "#303f56", "#92b9ee")
            if dark else
            ("#f5f6f8", "#ffffff", "#eef0f4", "#202733", "#637083", "#e1e5eb", "#e4ecf7", "#3568b0")
        )
        names = ("base", "surface", "panel", "ink", "muted", "line", "selected", "accent")
        palette = "\n".join(f"@define-color {name} {color};" for name, color in zip(names, colors))
        resource = Path(__file__).parent / "resources" / "style.css"
        self.css.load_from_data((palette + "\n" + resource.read_text()).encode())

    def rebuild_window(self, old_window):
        width, height = old_window.get_size()
        maximized = old_window.is_maximized()
        selected_group = old_window.selected_group
        favorites_view = old_window.favorites_view
        query = old_window.query
        status_filter = old_window.status_filter
        sort_order = old_window.sort_order
        try:
            window = MainWindow(self)
        except (ConfigError, OSError, ValueError) as exc:
            old_window.error_dialog(str(exc))
            return False
        window.resize(width, height)
        window.selected_group = selected_group if selected_group in window.ordered_groups() else None
        window.favorites_view = favorites_view
        window.query = query
        window.search.set_text(query)
        window.filter_selector.set_active_id(status_filter)
        window.sort_selector.set_active_id(sort_order)
        window.rebuild_groups()
        if maximized:
            window.maximize()
        old_window.destroy()
        window.present()
        return False

    def do_activate(self) -> None:
        window = self.props.active_window
        if not window:
            try:
                window = MainWindow(self)
            except (ConfigError, OSError, ValueError) as exc:
                dialog = Gtk.MessageDialog(modal=True, message_type=Gtk.MessageType.ERROR,
                                           buttons=Gtk.ButtonsType.CLOSE, text=_("The workspace could not be opened"))
                dialog.format_secondary_text(str(exc))
                dialog.run()
                dialog.destroy()
                self.quit()
                return
        window.present()

    def show_about(self, *_args) -> None:
        dialog = Gtk.AboutDialog(
            transient_for=self.props.active_window,
            modal=True,
            program_name="ConfiSSH",
            version=__version__,
            comments=_("OpenSSH connections are managed directly in your existing config files."),
            license_type=Gtk.License.MIT_X11,
        )
        dialog.run()
        dialog.destroy()


def main() -> int:
    return ConfiSSHApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
