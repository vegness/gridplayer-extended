from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QRect, QSize
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from gridplayer.player.managers.mini_window import (
    MINI_MIN_SIZE,
    MiniWindowManager,
)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


# The windows the running test has opened, drained and closed by
# `_open_windows` when it ends.
_OPENED: list[QWidget] = []


@pytest.fixture(autouse=True)
def _open_windows():
    """Close every window a test opened when it ends.

    One QApplication is held open for the whole run, so a window left
    shown is still there for the next test -- and a manager puts an event
    filter on the window it floats over, so one left behind is an event
    filter pointing at a window that has since gone. Closing here keeps
    each test to itself.
    """
    del _OPENED[:]

    yield

    for widget in _OPENED:
        widget.close()
        widget.deleteLater()

    del _OPENED[:]

    QApplication.processEvents()


class _Driver:
    """Enough of a video driver to hear the view asked for again."""

    def __init__(self):
        self.view_adjustments = 0

    def adjust_view(self):
        self.view_adjustments += 1


class _Block(QWidget):
    def __init__(self, video_id, parent=None):
        super().__init__(parent)
        self.id = video_id
        self.video_id = video_id
        self.video_driver = _Driver()


class _Blocks:
    def __init__(self, blocks):
        self._blocks = blocks

    @property
    def video_ids(self):
        return [b.video_id for b in self._blocks]

    def by_video_id(self, video_id):
        return next((b for b in self._blocks if b.video_id == video_id), None)

    def blocks_for_ids(self, video_ids):
        return [b for i in video_ids if (b := self.by_video_id(i)) is not None]

    def __bool__(self):
        return bool(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __len__(self):
        return len(self._blocks)


def _manager(blocks, active):
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    _OPENED.append(parent)

    grid_calls = []

    ctx = SimpleNamespace(
        is_single_mode=False,
        is_mini_mode=False,
        active_block=active,
        video_blocks=_Blocks(blocks),
        commands=SimpleNamespace(
            grid_layout_without_mini=lambda vid: grid_calls.append(("without", vid)),
            grid_layout_with_mini_back=lambda: grid_calls.append(("back", None)),
        ),
    )
    manager = MiniWindowManager(context=ctx, parent=parent)
    manager._keep = (parent, *blocks)
    manager._grid_calls = grid_calls
    return manager


def test_available_only_with_a_video_to_float():
    one = _Block("a")
    manager = _manager([one], one)
    assert manager.is_mini_mode_available() is False


def test_available_with_two_videos():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    assert manager.is_mini_mode_available() is True


def test_no_active_block_is_not_available():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], None)
    assert manager.is_mini_mode_available() is False


def test_toggle_does_nothing_when_unavailable():
    one = _Block("a")
    manager = _manager([one], one)

    manager.toggle_mini_video()

    assert manager._ctx.is_mini_mode is False
    assert manager._window is None


def test_turning_on_floats_the_active_video():
    a, b, c = _Block("a"), _Block("b"), _Block("c")
    manager = _manager([a, b, c], b)

    manager.mini_mode_on()

    assert manager._ctx.is_mini_mode is True
    assert manager._block is b
    assert b.parent() is manager._window
    assert manager._window.isVisible()
    # the grid was drawn without the floating cell
    assert manager._grid_calls == [("without", "b")]


def test_turning_off_puts_the_video_back():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], b)

    manager.mini_mode_on()
    manager.mini_mode_off()

    assert manager._ctx.is_mini_mode is False
    assert b.parent() is manager.parent()
    assert not manager._window.isVisible()
    assert manager._grid_calls[-1] == ("back", None)


def test_the_video_going_into_the_window_has_its_view_put_back():
    """The surface is placed by a view adjustment, and a reparent needs one.

    The window is laid out before the video goes in, and the video's frame
    resized to it; without the adjustment the native surface stays at the
    size it had in the grid, a grey pane where the picture should be.
    """
    a, b, c = _Block("a"), _Block("b"), _Block("c")
    manager = _manager([a, b, c], b)

    before = b.video_driver.view_adjustments
    manager.mini_mode_on()

    assert b.video_driver.view_adjustments > before


def test_a_redraw_under_the_window_sizes_the_video_to_it_again():
    """The grid is drawn again after the video has moved into the window.

    That draw can give the video a different size, so the window asks for the
    view once more on it -- the second thing that left the first click grey.
    """
    a, b, c = _Block("a"), _Block("b"), _Block("c")
    manager = _manager([a, b, c], b)
    manager.mini_mode_on()

    b.video_driver.view_adjustments = 0
    manager._window.resize(500, 400)
    manager.reload_window()

    assert b.video_driver.view_adjustments > 0
    assert b.size() == manager._window.content_rect().size()


def test_a_redraw_while_not_floating_is_left_alone():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)

    b.video_driver.view_adjustments = 0
    manager.reload_window()

    assert b.video_driver.view_adjustments == 0


def test_toggle_off_when_already_on():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)

    manager.mini_mode_on()
    manager.toggle_mini_video()

    assert manager._ctx.is_mini_mode is False


def test_leaving_when_only_one_video_left():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    manager.set_video_count(1)

    assert manager._ctx.is_mini_mode is False


def test_staying_when_videos_remain():
    a, b, c = _Block("a"), _Block("b"), _Block("c")
    manager = _manager([a, b, c], a)
    manager.mini_mode_on()

    manager.set_video_count(2)

    assert manager._ctx.is_mini_mode is True


def test_mini_state_is_none_when_off():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    assert manager.mini_state() is None


def test_mini_state_is_a_share_of_the_player():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    manager._window.setGeometry(QRect(100, 100, 400, 300))
    state = manager.mini_state()

    assert state is not None
    assert state[2] == pytest.approx(0.4, abs=0.02)
    assert state[3] == pytest.approx(300 / 700, abs=0.02)


def test_applying_mini_state_puts_the_window_back():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    manager.apply_mini_state([0.1, 0.2, 0.5, 0.5])

    geo = manager._window.geometry()
    assert geo.x() == pytest.approx(100, abs=2)
    assert geo.y() == pytest.approx(140, abs=2)
    assert geo.width() == pytest.approx(500, abs=2)


def test_window_will_not_go_below_its_minimum():
    from PyQt5.QtCore import QPoint

    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    start = QPoint(500, 500)
    manager.window_resize_started(start)
    # drag the corner far up and to the left, past the minimum
    manager.window_resized(QPoint(-500, -500))

    assert manager._window.width() >= MINI_MIN_SIZE.width()
    assert manager._window.height() >= MINI_MIN_SIZE.height()
    manager.window_resize_finished()
    manager.mini_mode_off()


def test_drag_moves_the_window_by_the_mouse_delta():
    from PyQt5.QtCore import QPoint

    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()
    manager._window.setGeometry(QRect(100, 100, 300, 200))

    manager.window_drag_started(QPoint(0, 0))
    manager.window_dragged(QPoint(50, 30))

    assert manager._window.pos() == QPoint(150, 130)


def test_a_single_video_has_no_place_to_float_over():
    one = _Block("a")
    manager = _manager([one], one)

    manager.mini_mode_on()

    assert manager._ctx.is_mini_mode is False


def test_a_closing_player_lets_go_of_the_window():
    """The window is given back on close, so nothing is left dangling."""
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    manager.cleanup()

    assert manager._ctx.is_mini_mode is False
    assert manager._window is None


def test_mini_window_minimum_size():
    assert MINI_MIN_SIZE == QSize(160, 90)


def test_the_window_paints_without_a_type_error():
    """Painting the border is the one thing a shown window always does.

    A float border gave ``QRect.adjusted`` a float inset and threw the paint
    over; drawing to a pixmap is the same code path without a desktop.
    """
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()
    manager._window.resize(300, 200)

    pixmap = QPixmap(manager._window.size())
    manager._window.render(pixmap)


def test_the_window_leaves_its_title_bar_clear_for_the_video():
    """The video sits below the title bar, not over it.

    The video is a widget over the window and takes the mouse of what it
    covers: were it over the bar there would be no bar to take the window by.
    """
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    window = manager._window
    window.resize(400, 300)
    window.resizeEvent(None)

    content = window.content_rect()

    assert content.top() >= window.TITLE_HEIGHT
    assert content.right() <= window.width() - window.RESIZE_GRIP
    assert content.bottom() <= window.height() - window.RESIZE_GRIP
    # `a` is the active cell, so the one that floats
    assert a.geometry() == content


def test_the_window_says_it_is_a_floating_window():
    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    manager.mini_mode_on()

    assert manager._window.is_floating_window is True


def test_a_press_on_the_window_is_not_a_press_on_the_video():
    """The floating window is elsewhere, as far as the player's own mouse is.

    A drag on it is the window's, not the video's: left to the video it would
    be a move-to-another-cell drag, and the window never moves.
    """
    from gridplayer.player.managers.base import ManagerBase

    a, b = _Block("a"), _Block("b")
    manager = _manager([a, b], a)
    # a cell left in the grid is a child of the player, as a real one is
    b.setParent(manager.parent())
    manager.mini_mode_on()

    window = manager._window
    assert ManagerBase.is_elsewhere(manager, window) is True
    # the video inside it too, not only the window itself
    assert ManagerBase.is_elsewhere(manager, a) is True
    # the video left in the grid is not
    assert ManagerBase.is_elsewhere(manager, b) is False
