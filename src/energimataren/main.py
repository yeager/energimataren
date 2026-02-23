"""Energimätaren - Visual energy level tracker for children."""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk, Gio
import gettext, locale, os, json, time, math

__version__ = "0.1.0"
APP_ID = "se.danielnylander.energimataren"
LOCALE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'share', 'locale')
if not os.path.isdir(LOCALE_DIR): LOCALE_DIR = "/usr/share/locale"
try:
    locale.bindtextdomain(APP_ID, LOCALE_DIR)
    gettext.bindtextdomain(APP_ID, LOCALE_DIR)
    gettext.textdomain(APP_ID)
except Exception: pass
_ = gettext.gettext

LEVELS = [
    {"name": N_("Very Low"), "icon": "😴", "color": "#3b82f6", "value": 1},
    {"name": N_("Low"), "icon": "😐", "color": "#06b6d4", "value": 2},
    {"name": N_("Medium"), "icon": "🙂", "color": "#22c55e", "value": 3},
    {"name": N_("High"), "icon": "😊", "color": "#f59e0b", "value": 4},
    {"name": N_("Very High"), "icon": "🤩", "color": "#ef4444", "value": 5},
]

STRATEGIES = {
    1: [N_("Take a break"), N_("Drink some water"), N_("Ask for help")],
    2: [N_("Move around a little"), N_("Have a snack"), N_("Talk to someone")],
    3: [N_("Keep going!"), N_("You're doing great!")],
    4: [N_("Focus that energy"), N_("Try a calm activity next")],
    5: [N_("Take deep breaths"), N_("Go for a walk"), N_("Use a fidget toy")],
}

def N_(s): return s


class EnergyGauge(Gtk.DrawingArea):
    """Visual energy thermometer."""
    def __init__(self):
        super().__init__()
        self._level = 3
        self.set_content_width(80)
        self.set_content_height(300)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, width, height):
        margin = 10
        bar_w = width - 2 * margin
        bar_h = height - 2 * margin
        
        # Background
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.2)
        cr.rectangle(margin, margin, bar_w, bar_h)
        cr.fill()
        
        # Filled portion
        fraction = self._level / 5.0
        fill_h = bar_h * fraction
        
        # Gradient from blue (bottom) to red (top)
        r = 0.2 + 0.8 * fraction
        g = 0.8 - 0.4 * fraction
        b = 1.0 - 0.8 * fraction
        cr.set_source_rgba(r, g, b, 0.8)
        cr.rectangle(margin, margin + bar_h - fill_h, bar_w, fill_h)
        cr.fill()
        
        # Level markers
        for i in range(5):
            y = margin + bar_h - (bar_h * (i + 1) / 5)
            cr.set_source_rgba(1, 1, 1, 0.5)
            cr.move_to(margin, y)
            cr.line_to(margin + bar_w, y)
            cr.set_line_width(1)
            cr.stroke()

    def set_level(self, level):
        self._level = level
        self.queue_draw()


class EnergiWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Energimätaren"))
        self.set_default_size(500, 550)
        self._log = []
        self._config_dir = os.path.join(GLib.get_user_config_dir(), "energimataren")
        os.makedirs(self._config_dir, exist_ok=True)
        self._load_log()

        
        # Easter egg state
        self._egg_clicks = 0
        self._egg_timer = None

        header = Adw.HeaderBar()
        
        # Add clickable app icon for easter egg
        app_btn = Gtk.Button()
        app_btn.set_icon_name("se.danielnylander.energimataren")
        app_btn.add_css_class("flat")
        app_btn.set_tooltip_text(_("Energimataren"))
        app_btn.connect("clicked", self._on_icon_clicked)
        header.pack_start(app_btn)

        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu = Gio.Menu()
        menu.append(_("History"), "win.history")
        menu.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        hist_action = Gio.SimpleAction.new("history", None)
        hist_action.connect("activate", self._show_history)
        self.add_action(hist_action)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)

        # Gauge
        self._gauge = EnergyGauge()
        content.append(self._gauge)

        # Right side
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right.set_hexpand(True)

        q_label = Gtk.Label(label=_("How is your energy right now?"))
        q_label.add_css_class("title-3")
        q_label.set_wrap(True)
        right.append(q_label)

        # Level buttons
        for i, level in enumerate(LEVELS):
            btn = Gtk.Button()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            icon = Gtk.Label(label=level["icon"])
            icon.add_css_class("title-3")
            box.append(icon)
            name = Gtk.Label(label=_(level["name"]))
            name.add_css_class("title-4")
            box.append(name)
            btn.set_child(box)
            btn.add_css_class("card")
            btn.connect("clicked", self._on_level_selected, level["value"])
            right.append(btn)

        # Strategy display
        self._strategy_label = Gtk.Label()
        self._strategy_label.add_css_class("dim-label")
        self._strategy_label.set_wrap(True)
        self._strategy_label.set_visible(False)
        right.append(self._strategy_label)

        content.append(right)
        main_box.append(content)

        # Status bar
        self._status = Gtk.Label(label=_("Choose your energy level"))
        self._status.add_css_class("dim-label")
        self._status.set_margin_bottom(8)
        main_box.append(self._status)

        self.set_content(main_box)

    def _on_level_selected(self, btn, value):
        self._gauge.set_level(value)
        level = LEVELS[value - 1]
        
        entry = {"level": value, "name": level["name"], "time": time.strftime("%H:%M")}
        self._log.append(entry)
        self._save_log()
        
        self._status.set_text(_("Energy: %s %s") % (level["icon"], _(level["name"])))
        
        strategies = STRATEGIES.get(value, [])
        if strategies:
            tip = _(strategies[0]) if strategies else ""
            self._strategy_label.set_text("💡 " + tip)
            self._strategy_label.set_visible(True)
        else:
            self._strategy_label.set_visible(False)

    def _load_log(self):
        path = os.path.join(self._config_dir, "log.json")
        try:
            with open(path) as f:
                self._log = json.load(f)
        except Exception:
            self._log = []

    def _save_log(self):
        path = os.path.join(self._config_dir, "log.json")
        with open(path, 'w') as f:
            json.dump(self._log[-50:], f, ensure_ascii=False)

    def _show_history(self, action, param):
        dialog = Adw.Dialog()
        dialog.set_title(_("Energy History"))
        dialog.set_content_width(350)
        dialog.set_content_height(400)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_bottom(16)
        
        header = Adw.HeaderBar()
        
        # Add clickable app icon for easter egg
        app_btn = Gtk.Button()
        app_btn.set_icon_name("se.danielnylander.energimataren")
        app_btn.add_css_class("flat")
        app_btn.set_tooltip_text(_("Energimataren"))
        app_btn.connect("clicked", self._on_icon_clicked)
        header.pack_start(app_btn)

        header.set_show_end_title_buttons(True)
        box.append(header)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        for entry in reversed(self._log[-20:]):
            level = LEVELS[entry["level"] - 1]
            row = Gtk.Label(label=f"{entry.get('time', '?')} — {level['icon']} {_(level['name'])}", xalign=0)
            lst.append(row)
        
        if not self._log:
            lst.append(Gtk.Label(label=_("No entries yet")))
        
        scroll.set_child(lst)
        box.append(scroll)
        dialog.set_child(box)
        dialog.present(self)

    def _on_icon_clicked(self, *args):
        """Handle clicks on app icon for easter egg."""
        self._egg_clicks += 1
        if self._egg_timer:
            GLib.source_remove(self._egg_timer)
        self._egg_timer = GLib.timeout_add(500, self._reset_egg)
        if self._egg_clicks >= 7:
            self._trigger_easter_egg()
            self._egg_clicks = 0

    def _reset_egg(self):
        """Reset easter egg click counter."""
        self._egg_clicks = 0
        self._egg_timer = None
        return False

    def _trigger_easter_egg(self):
        """Show the secret easter egg!"""
        try:
            # Play a fun sound
            import subprocess
            subprocess.Popen(['paplay', '/usr/share/sounds/freedesktop/stereo/complete.oga'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            # Fallback beep
            try:
                subprocess.Popen(['pactl', 'play-sample', 'bell'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

        # Show confetti message
        toast = Adw.Toast.new(_("🎉 Du hittade hemligheten!"))
        toast.set_timeout(3)
        
        # Create toast overlay if it doesn't exist
        if not hasattr(self, '_toast_overlay'):
            content = self.get_content()
            self._toast_overlay = Adw.ToastOverlay()
            self._toast_overlay.set_child(content)
            self.set_content(self._toast_overlay)
        
        self._toast_overlay.add_toast(toast)



class EnergiApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self._on_about)
        self.add_action(about)

    def _on_activate(self, app):
        win = EnergiWindow(application=app)
        win.present()

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name=_("Energimätaren"),
            application_icon=APP_ID,
            version=__version__,
            developer_name="Daniel Nylander",
            website="https://github.com/yeager/energimataren",
            license_type=Gtk.License.GPL_3_0,
            comments=_("Visual energy level tracker for children with NPF"),
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
        )
        about.present(self.get_active_window())

def main():
    app = EnergiApp()
    app.run()

if __name__ == "__main__":
    main()
