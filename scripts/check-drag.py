"""Exercise real X11 pointer dragging, using an isolated config and preferences."""
import ctypes
import copy
import os
import tempfile
import time
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="confissh-drag-") as directory:
    os.environ["GDK_BACKEND"] = "x11"
    os.environ["XDG_CONFIG_HOME"] = directory
    os.environ["CONFISSH_LANGUAGE"] = "en"
    config = Path(directory) / "config"
    config.write_text("Host a\n HostName localhost\n\nHost b\n HostName localhost\n")
    os.environ["CONFISSH_CONFIG"] = str(config)
    from confissh.app import ConfiSSHApplication, Gtk, GLib

    app = ConfiSSHApplication()
    app.set_application_id("io.github.confissh.ConfiSSH.dragtest")
    app.register(None)
    app.activate()
    window = app.props.active_window
    data = copy.deepcopy(window.store.data)
    first = window.store.save_group(data, None, "Alpha")
    second = window.store.save_group(data, None, "Beta")
    window.save_metadata(data)

    def drain(seconds=0.2):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(0.01)

    window.present()
    drain(0.7)
    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    display = x11.XOpenDisplay(None)
    assert display, "X11 session required"

    def motion(x, y):
        xtst.XTestFakeMotionEvent(display, -1, x, y, 0)
        x11.XFlush(display)
        drain()

    def button(pressed, number=1):
        xtst.XTestFakeButtonEvent(display, number, pressed, 0)
        x11.XFlush(display)
        drain()

    events = []
    window.connect("button-press-event", lambda _, event: events.append(("press", event.x_root, event.y_root)) or False)
    for row in window.group_list.get_children():
        row.drag_surface.connect("drag-begin", lambda *_: events.append("begin"))
        row.drag_surface.connect("drag-data-received", lambda *_: events.append("received"))
    origin = window.get_window().get_origin()
    source = window.group_list.get_row_at_index(1)
    target = window.group_list.get_row_at_index(0)
    sx, sy = source.translate_coordinates(window, 24, source.get_allocated_height() // 2)
    tx, ty = target.translate_coordinates(window, 24, 5)
    sx, sy, tx, ty = sx + origin.x, sy + origin.y, tx + origin.x, ty + origin.y
    print("Pointer path:", (sx, sy), (tx, ty))
    try:
        motion(sx, sy)
        button(1)
        for step in range(1, 9):
            motion(round(sx + (tx - sx) * step / 8), round(sy + (ty - sy) * step / 8))
        button(0)
        drain(0.5)
        print("Drag signals:", events)
        print("Order:", window.ordered_groups())
        assert window.ordered_groups() == ["Beta", "Alpha"]
        from confissh.storage import MetadataStore
        groups = MetadataStore(window.store.path).data["groups"]
        assert groups[second]["order"] < groups[first]["order"]
        before = config.read_bytes()
        connection_id = window.doc.entries[0].connection_id
        for destination in ("Beta", "Alpha"):
            source_row = next(row for row in window.host_list.get_children()
                              if row.entry.connection_id == connection_id)
            target_row = next(row for row in window.group_list.get_children()
                              if row.group_name == destination)
            origin = window.get_window().get_origin()
            sx, sy = source_row.translate_coordinates(window, 90, 25)
            tx, ty = target_row.translate_coordinates(window, 50, target_row.get_allocated_height() // 2)
            sx, sy = sx + origin.x, sy + origin.y
            tx, ty = tx + origin.x, ty + origin.y
            motion(sx, sy)
            button(1)
            for step in range(1, 13):
                motion(round(sx + (tx - sx) * step / 12), round(sy + (ty - sy) * step / 12))
            button(0)
            drain(0.4)
            expected = {"Alpha": first, "Beta": second}[destination]
            assert MetadataStore(window.store.path).data["connections"][connection_id]["group_id"] == expected
            assert config.read_bytes() == before
            assert window.doc.entries[0].connection_id == connection_id
        # Dragging the last member out of a selected group removes its row.
        assert window.move_connection(connection_id, first)
        window.selected_group = "Alpha"
        window.rebuild_groups()
        drain()
        source_row = window.host_list.get_children()[0]
        target_row = next(row for row in window.group_list.get_children() if row.group_name == "Beta")
        sx, sy = source_row.translate_coordinates(window, 90, 25)
        tx, ty = target_row.translate_coordinates(window, 50, 15)
        motion(sx + origin.x, sy + origin.y)
        button(1)
        for step in range(1, 13):
            motion(round(sx + (tx - sx) * step / 12) + origin.x,
                   round(sy + (ty - sy) * step / 12) + origin.y)
        button(0)
        drain(0.4)
        assert window.is_empty_group()
        assert window.empty.get_visible()
        assert window.empty_action.get_label() == "Add connection to group"
        assert config.read_bytes() == before
        print("PASS: connection drops onto empty/populated groups; SSH unchanged")
        row = next(row for row in window.group_list.get_children() if row.group_name == "Alpha")
        x, y = row.translate_coordinates(window, 55, row.get_allocated_height() // 2)
        motion(x + origin.x, y + origin.y)
        button(1, 3)
        button(0, 3)
        assert window.group_menu.get_visible()
        rename = next(item for item in window.group_menu.get_children()
                      if isinstance(item, Gtk.MenuItem) and item.get_label() == "Rename…")
        records_before = copy.deepcopy(window.store.data["connections"])
        attempts = iter(["", "Beta", "Renamed Alpha"])
        def fill_rename():
            for widget in Gtk.Window.list_toplevels():
                if isinstance(widget, Gtk.Dialog) and widget.get_title() == "Edit group":
                    name = next(child for child in widget.get_content_area().get_children()
                                if isinstance(child, Gtk.Entry))
                    value = next(attempts)
                    assert window.store.data["groups"][first]["name"] == "Alpha"
                    name.set_text(value)
                    widget.response(Gtk.ResponseType.OK)
                    return value != "Renamed Alpha"
            return True
        GLib.timeout_add(100, fill_rename)
        window.group_menu.popdown()
        rename.activate()
        assert window.store.data["groups"][first]["name"] == "Renamed Alpha"
        assert window.selected_group == "Renamed Alpha"
        assert window.store.data["connections"] == records_before
        assert config.read_bytes() == before
        assert MetadataStore(window.store.path).data["groups"][first]["name"] == "Renamed Alpha"
        print("PASS: real right-click menu, rename validation, stable group ID and assignments")
        window.navigation.select_row(window.navigation.get_row_at_index(0))
        drain()
        for group_name, expected_id in (("Renamed Alpha", first), ("Remove group assignment", None)):
            row = next(row for row in window.host_list.get_children() if row.entry.connection_id == connection_id)
            x, y = row.translate_coordinates(window, 90, 25)
            origin = window.get_window().get_origin()
            motion(x + origin.x, y + origin.y)
            button(1, 3)
            button(0, 3)
            assert row.context_menu.get_visible()
            submenu = next(item for item in row.context_menu.get_children()
                           if isinstance(item, Gtk.MenuItem) and item.get_label() == "Change group").get_submenu()
            item = next(item for item in submenu.get_children() if item.get_label() == group_name)
            row.context_menu.popdown()
            item.activate()
            drain()
            assert MetadataStore(window.store.path).data["connections"][connection_id]["group_id"] == expected_id
            assert config.read_bytes() == before
            if expected_id:
                window.selected_group = group_name
                window.rebuild_groups()
                drain()
        assert window.is_empty_group()
        print("PASS: real connection right-click, move to group, remove assignment and refresh selected group")
        print("PASS: real pointer drag and persistence")
    finally:
        button(0)
        x11.XCloseDisplay(display)
        window.destroy()
        app.quit()
