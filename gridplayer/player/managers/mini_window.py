from PyQt5.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from gridplayer.player.managers.base import ManagerBase
from gridplayer.widgets.cell_chrome import chrome_color

# How small a floating window may be dragged: below this its overlay's
# controls stop fitting, and a video under it is no use to look at.
MINI_MIN_SIZE = QSize(160, 90)

# Where the window comes up at first, as a share of the player's own size,
# and how far in from its corner.
MINI_DEFAULT_SHARE = 0.34
MINI_DEFAULT_MARGIN = 16

# How far the window may go past the player's edge, so it cannot be dragged
# out of reach.
MINI_EDGE_KEEP = 60


def _reapply_video_view(block):
    """Have a video's surface take the size its frame now has.

    Only for the callers here: a video with no driver yet, or one that was
    never given a window to draw into, has nothing to place.
    """

    driver = getattr(block, "video_driver", None)

    if driver is not None and hasattr(driver, "adjust_view"):
        driver.adjust_view()


class MiniWindowManager(ManagerBase):
    """One video floating over the rest, the others laid out without it.

    The floating video is the active cell, shown in a window of its own over
    the player: it can be moved and resized freely, and what it covers is
    still there behind it. The rest keep their arrangement as if it were
    never there -- a 2x2 grid of four draws as a 3-cell auto grid while the
    fourth floats.
    """

    mode_changed = pyqtSignal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._ctx.is_mini_mode = False

        self._window: MiniVideoWindow | None = None
        self._block = None
        self._drag_origin: QPoint | None = None
        self._drag_start: QPoint | None = None
        self._resize_origin: QRect | None = None

    def init(self):
        self.parent().installEventFilter(self)

    @property
    def commands(self):
        return {
            "toggle_mini_video": self.toggle_mini_video,
            "is_mini_mode": lambda: self._ctx.is_mini_mode,
            "is_mini_mode_available": self.is_mini_mode_available,
            "mini_mode_on": self.mini_mode_on,
            "mini_mode_off": self.mini_mode_off,
        }

    @property
    def event_map(self):
        # The player resized under the floating window: keep it reachable.
        return {QEvent.Resize: self._on_parent_resized}

    def is_mini_mode_available(self):
        """A video to float, and something left over to arrange without it.

        With a single cell there is nothing to float it over, and the grid it
        is taken out of would be empty.
        """
        return self._ctx.active_block is not None and len(self._ctx.video_blocks) > 1

    def toggle_mini_video(self):
        if self._ctx.is_mini_mode:
            self.mini_mode_off()
            return

        if not self.is_mini_mode_available():
            return

        self.mini_mode_on()

    # --- lifecycle ---

    def mini_mode_on(self):
        if self._ctx.is_mini_mode or not self.is_mini_mode_available():
            return

        self._ctx.is_mini_mode = True
        self._block = self._ctx.active_block

        self._ensure_window()
        self._window.setGeometry(self._default_geometry())

        # The grid first, so the others have taken their places by the time
        # the floating cell is a window of its own and painted over them.
        self._ctx.commands.grid_layout_without_mini(self._block.video_id)

        # Shown and laid out before the video goes into it: a hardware
        # video's surface is sized from the frame's size where it is put, and
        # a frame put into a window that has not been laid out yet is sized
        # from nothing.
        self._window.show()
        self._window.raise_()

        self._attach(self._block)

        self.mode_changed.emit()

    def mini_mode_off(self):
        if not self._ctx.is_mini_mode:
            return

        self._ctx.is_mini_mode = False

        block = self._block
        self._detach(block)
        self._block = None

        if self._window is not None:
            self._window.hide()

        if block is not None:
            block.show()

        self._ctx.commands.grid_layout_with_mini_back()

        self.mode_changed.emit()

    def set_video_count(self, video_count):
        """Leave mini mode when the number of videos changes.

        The cells' places are rebuilt on a count change, and with one video
        left there is nothing to float it over.
        """
        if self._ctx.is_mini_mode and video_count < 2:
            self.mini_mode_off()

    def reload_window(self):
        """The grid was drawn again under the floating window: put it back on
        top of it, and have the video take the size it was left with.

        Turning mini mode on emits mode_changed, which draws the grid again
        -- after the video has been moved into the window. That draw gives
        the placed cells the grid's sizes; the floating cell was not among
        them (see GridManager._sync_block_visibility), so it is put back to
        the window's size here, and its surface asked for the same.
        """
        if not self._ctx.is_mini_mode or self._window is None:
            return

        self._window.raise_()

        if self._block is not None:
            self._block.setGeometry(self._window.content_rect())
            _reapply_video_view(self._block)

    def cleanup(self):
        """The player is closing: put the floating video back and let go of
        the window, so it is destroyed in order rather than left dangling."""
        if self._ctx.is_mini_mode:
            self.mini_mode_off()

        if self._window is not None:
            self.parent().removeEventFilter(self)
            self._window.deleteLater()
            self._window = None

    # --- the window ---

    def _ensure_window(self):
        if self._window is None:
            self._window = MiniVideoWindow(
                self.parent(),
                handlers={
                    "block": lambda: self._block,
                    "drag_started": self.window_drag_started,
                    "dragged": self.window_dragged,
                    "drag_finished": self.window_drag_finished,
                    "resize_started": self.window_resize_started,
                    "resized": self.window_resized,
                    "resize_finished": self.window_resize_finished,
                },
            )

    def _default_geometry(self) -> QRect:
        parent = self.parent().rect()
        size = QSize(
            max(int(parent.width() * MINI_DEFAULT_SHARE), MINI_MIN_SIZE.width()),
            max(int(parent.height() * MINI_DEFAULT_SHARE), MINI_MIN_SIZE.height()),
        )
        return QRect(
            parent.right() - size.width() - MINI_DEFAULT_MARGIN,
            parent.bottom() - size.height() - MINI_DEFAULT_MARGIN,
            size.width(),
            size.height(),
        )

    def _attach(self, block):
        block.setParent(self._window)
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        block.setGeometry(self._window.content_rect())
        block.show()

        # A reparent makes the frame build its window again, and a hardware
        # video's surface is only ever placed by a view adjustment -- which
        # a resize alone does not always reach. Ask for one directly, so the
        # surface lands in the window rather than staying where it was.
        _reapply_video_view(block)

    def _detach(self, block):
        if block is None:
            return

        block.setParent(self.parent())
        block.hide()

    # --- moving and resizing, from the window's own mouse ---

    def window_drag_started(self, global_pos):
        self._drag_origin = self._window.pos()
        self._drag_start = global_pos

    def window_dragged(self, global_pos):
        if self._drag_origin is None:
            return

        self._window.move(self._drag_origin + (global_pos - self._drag_start))

    def window_drag_finished(self):
        self._drag_origin = None
        self._drag_start = None

    def window_resize_started(self, global_pos):
        self._resize_origin = self._window.geometry()
        self._drag_start = global_pos

    def window_resized(self, global_pos):
        if self._resize_origin is None:
            return

        delta = global_pos - self._drag_start
        self._window.resize(
            QSize(
                max(self._resize_origin.width() + delta.x(), MINI_MIN_SIZE.width()),
                max(self._resize_origin.height() + delta.y(), MINI_MIN_SIZE.height()),
            )
        )

    def window_resize_finished(self):
        self._resize_origin = None
        self._drag_start = None

    # --- state ---

    def mini_state(self):
        """Where the window is, as it is to be saved: its place and size
        within the player, as a share of it, so it comes back the same
        whatever the player's own size is."""
        if self._window is None or not self._ctx.is_mini_mode:
            return None

        parent = self.parent().rect()
        if parent.width() <= 0 or parent.height() <= 0:
            return None

        geo = self._window.geometry()
        return [
            geo.x() / parent.width(),
            geo.y() / parent.height(),
            geo.width() / parent.width(),
            geo.height() / parent.height(),
        ]

    def apply_mini_state(self, state):
        if not state or self._window is None:
            return

        parent = self.parent().rect()
        self._window.setGeometry(
            QRect(
                int(state[0] * parent.width()),
                int(state[1] * parent.height()),
                max(int(state[2] * parent.width()), MINI_MIN_SIZE.width()),
                max(int(state[3] * parent.height()), MINI_MIN_SIZE.height()),
            )
        )

    def _on_parent_resized(self, event):
        if not self._ctx.is_mini_mode or self._window is None:
            return False

        parent = self.parent().rect()
        geo = self._window.geometry()
        x = min(geo.x(), max(parent.width() - MINI_EDGE_KEEP, 0))
        y = min(geo.y(), max(parent.height() - MINI_EDGE_KEEP, 0))
        if (x, y) != (geo.x(), geo.y()):
            self._window.move(x, y)

        return False


class MiniVideoWindow(QWidget):
    """The window one video floats in.

    A child of the player rather than a top-level window of its own, so it
    goes where the player goes and stays over the videos under it. Drag it by
    its title bar, resize it from its bottom right corner.

    It is given the calls it makes back, not the manager that made it, so the
    window holds nothing that holds the window.
    """

    TITLE_HEIGHT = 16
    RESIZE_GRIP = 18
    BORDER = 3

    # A press on it is not a press on the video under it (see
    # ManagerBase.is_elsewhere): the drags and the drops are its own.
    is_floating_window = True

    def __init__(self, parent, handlers, **kwargs):
        super().__init__(parent, **kwargs)

        self._handlers = handlers

        self.setMouseTracking(True)
        self.setMinimumSize(MINI_MIN_SIZE)

        self._mode = None
        self._press_pos = None

    @property
    def _block(self):
        return self._handlers["block"]()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        chrome = chrome_color(self, alpha=180)

        # The bar to take it by, so it is plain where the window is dragged
        # from rather than the video filling it edge to edge.
        painter.fillRect(
            0, 0, self.width(), self.TITLE_HEIGHT, chrome_color(self, alpha=90)
        )

        pen = QPen(chrome)
        pen.setWidthF(self.BORDER)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        inset = self.BORDER // 2
        painter.drawRect(self.rect().adjusted(inset, inset, -inset, -inset))
        painter.end()

    def content_rect(self) -> QRect:
        """Where the video goes: the window, less the title bar and the
        resize corner, so the bar and the corner stay clear to take the
        window by and to drag it bigger.

        The video is a widget over the window, so whatever of the window it
        covers it also takes the mouse of: the parts left out are the parts
        of the window that answer to its own mouse.
        """

        return self.rect().adjusted(
            0, self.TITLE_HEIGHT, -self.RESIZE_GRIP, -self.RESIZE_GRIP
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)

        block = self._block
        if block is not None:
            block.setGeometry(self.content_rect())

    def _is_in_grip(self, pos):
        return (
            pos.x() >= self.width() - self.RESIZE_GRIP
            and pos.y() >= self.height() - self.RESIZE_GRIP
        )

    def _is_in_title(self, pos):
        return pos.y() <= self.TITLE_HEIGHT

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        pos = event.pos()
        self._press_pos = pos

        if self._is_in_grip(pos):
            self._mode = "resize"
            self._handlers["resize_started"](event.globalPos())
        elif self._is_in_title(pos):
            self._mode = "move"
            self._handlers["drag_started"](event.globalPos())

        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.pos()

        if self._mode == "resize":
            self._handlers["resized"](event.globalPos())
        elif self._mode == "move":
            self._handlers["dragged"](event.globalPos())
        elif self._is_in_grip(pos):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._is_in_title(pos):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._mode == "resize":
            self._handlers["resize_finished"]()
        elif self._mode == "move":
            self._handlers["drag_finished"]()

        self._mode = None
        self.unsetCursor()
        event.accept()
