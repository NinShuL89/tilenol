import logging

from zorro.di import di, has_dependencies, dependency

from .keyregistry import KeyRegistry
from .window import Window
from .xcb import Core, Rectangle, XError
from .groups import GroupManager
from .commands import CommandDispatcher


log = logging.getLogger(__name__)


@has_dependencies
class EventDispatcher(object):

    keys = dependency(KeyRegistry, 'key-registry')
    xcore = dependency(Core, 'xcore')
    groupman = dependency(GroupManager, 'group-manager')

    def __init__(self):
        self.windows = {}
        self.frames = {}
        self.all_windows = {}

    def dispatch(self, ev):
        meth = getattr(self, 'handle_'+ev.__class__.__name__, None)
        if meth:
            meth(ev)
        else:
            print("EVENT", ev)

    def register_window(self, win):
        self.all_windows[win.wid] = win

    def handle_KeyPressEvent(self, ev):
        self.keys.dispatch_event(ev)

    def handle_KeyReleaseEvent(self, ev):
        pass  # nothing to do at the moment

    def handle_MapRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %x",
                ev.window)
        else:
            win.want.visible = True
            if not hasattr(win, 'group'):
                self.groupman.add_window(win)

    def handle_EnterNotifyEvent(self, ev):
        try:
            win = self.frames[ev.event]
        except KeyError:
            log.warning("Enter notify for non-existent window %x", ev.event)
        else:
            win.focus()

    def handle_LeaveNotifyEvent(self, ev):
        pass  # nothing to do at the moment

    def handle_MapNotifyEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Map notify for non-existent window %x",
                ev.window)
        else:
            win.real.visible = True

    def handle_UnmapNotifyEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Unmap notify for non-existent window %x",
                ev.window)
        else:
            win.real.visible = False
            if win.frame:
                win.ewmh.hiding_window(win)
                win.frame.hide()

    def handle_FocusInEvent(self, ev):
        try:
            win = self.all_windows[ev.event]
        except KeyError:
            log.warning("Focus request for non-existent window %x",
                ev.window)
        else:
            if(ev.mode not in (self.xcore.NotifyMode.Grab,
                               self.xcore.NotifyMode.Ungrab)
               and ev.detail != self.xcore.NotifyDetail.Pointer):
                win.focus_in()

    def handle_FocusOutEvent(self, ev):
        try:
            win = self.all_windows[ev.event]
        except KeyError:
            log.warning("Focus request for non-existent window %x",
                ev.window)
        else:
            if(ev.mode not in (self.xcore.NotifyMode.Grab,
                               self.xcore.NotifyMode.Ungrab)
               and ev.detail != self.xcore.NotifyDetail.Pointer):
                win.focus_out()

    def handle_CreateNotifyEvent(self, ev):
        win = di(self).inject(Window.from_notify(ev))
        if win.wid in self.windows:
            log.warning("Create notify for already existent window %x",
                win.wid)
            # TODO(tailhook) clean up old window
        if win.wid in self.all_windows:
            return
        self.windows[win.wid] = win
        self.all_windows[win.wid] = win
        if win.toplevel and not win.override:
            frm = win.reparent()
            self.frames[frm.wid] = frm
            self.all_windows[frm.wid] = frm

    def handle_ConfigureNotifyEvent(self, ev):
        pass

    def handle_ReparentNotifyEvent(self, ev):
        pass

    def handle_DestroyNotifyEvent(self, ev):
        try:
            win = self.all_windows.pop(ev.window)
        except KeyError:
            log.warning("Destroy notify for non-existent window %x",
                ev.window)
        else:
            self.windows.pop(ev.window, None)
            self.frames.pop(ev.window, None)
            if hasattr(win, 'group'):
                win.group.remove_window(win)
            win.destroyed()

    def handle_ConfigureRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %x",
                ev.window)
        else:
            win.update_size_request(ev)

    def handle_PropertyNotifyEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Property notify event for non-existent window %x",
                ev.window)
        else:
            win.update_property(ev.atom)

    def handle_ExposeEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Expose event for non-existent window %x",
                ev.window)
        else:
            win.expose(Rectangle(ev.x, ev.y, ev.width, ev.height))

    def handle_ClientMessageEvent(self, ev):
        type = self.xcore.atom[ev.type]
        import struct
        print("ClientMessage", ev, repr(type), struct.unpack('<5L', ev.data))


