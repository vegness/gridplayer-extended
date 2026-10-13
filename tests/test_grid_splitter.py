from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication, QWidget

from gridplayer.models.grid_state import GridState
from gridplayer.params.static import GridMode
from gridplayer.player.managers.grid import GridManager


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


# The windows the running test has opened, drained and closed by
# `_closed_windows` when it ends.
_OPENED: list[QWidget] = []


@pytest.fixture(autouse=True)
def _closed_windows():
    """Close the window each test laid its grid in.

    One QApplication runs the whole suite, so a window left open is still
    there for the next test, along with the splitter tree hung under it.
    """
    del _OPENED[:]

    yield

    for widget in _OPENED:
        widget.close()
        widget.deleteLater()

    del _OPENED[:]

    QApplication.processEvents()


class _Block(QWidget):
    def __init__(self, video_id, parent):
        super().__init__(parent)
        self.id = video_id
        self.video_id = video_id
        self.hidden_calls = 0
        self.shown_calls = 0

    def hide(self):
        self.hidden_calls += 1
        super().hide()

    def show(self):
        self.shown_calls += 1
        super().show()


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


def _make(count, *, is_resizable=False):
    """A grid manager over `count` cells, with the window they live in.

    The cells are parented to the window from the start: a widget with no
    parent is the only owner of its C++ object, and one held by nothing else
    is gone as soon as the name for it goes out of scope.
    """
    parent = QWidget()
    parent.resize(800, 600)
    _OPENED.append(parent)

    blocks = [_Block(f"v{n}", parent) for n in range(count)]

    manager = GridManager(
        context=SimpleNamespace(
            video_blocks=_Blocks(blocks),
            is_shuffle_on_load=False,
            is_single_mode=False,
            commands=SimpleNamespace(remove_video_blocks=lambda *_a, **_k: None),
        ),
        parent=parent,
    )
    manager._mode = GridMode.AUTO_ROWS
    manager._flow.ids = [b.video_id for b in blocks]
    manager._is_resizable = is_resizable
    manager._keep = (parent, blocks)
    return manager, blocks


def test_resizable_is_off_by_default():
    manager, _ = _make(0)
    assert manager._is_resizable is False


def test_set_resizable_rebuilds_grid():
    manager, _ = _make(4, is_resizable=False)

    manager.set_grid_resizable(True)

    assert manager._is_resizable is True
    assert manager._splitter_root is not None
    # The root splitter stacks rows, so it holds one child per row -- not one
    # per cell. A 2x2 grid is two rows, however many cells that is.
    assert manager._splitter_root.count() == manager.grid_dimensions.rows


def test_splitter_tree_has_a_row_splitter_per_row():
    manager, _ = _make(4, is_resizable=True)

    manager._render_video_grid()

    dims = manager.grid_dimensions
    assert len(manager._splitter_rows) == dims.rows
    assert manager._splitter_root is not None


def test_ratios_are_read_back_from_the_tree():
    manager, _ = _make(4, is_resizable=True)

    manager._render_video_grid()

    # A 2x2 grid: the seam that divides a row is the one worth reading back.
    row = manager._splitter_rows[0]
    row.setSizes([300, 100])
    state = manager.grid_state()

    by_key = dict(state.splitter_sizes)
    ratios = by_key["row:0"]
    assert len(ratios) == 2
    assert ratios[0] == pytest.approx(0.75, abs=0.01)
    assert ratios[1] == pytest.approx(0.25, abs=0.01)


def test_splitter_sizes_survive_a_state_round_trip():
    manager, _ = _make(4, is_resizable=True)
    manager._render_video_grid()

    manager._splitter_rows[0].setSizes([300, 100])
    saved = manager.grid_state()

    # a fresh manager, as a re-opened playlist would make
    other, _ = _make(4, is_resizable=True)
    other._render_video_grid()
    other._apply_splitter_sizes_state(saved.splitter_sizes)

    by_key = dict(saved.splitter_sizes)
    assert by_key["row:0"] == pytest.approx([0.75, 0.25], abs=0.01)

    restored = other._ratios_of(other._splitter_rows[0])
    assert restored[0] == pytest.approx(0.75, abs=0.02)
    assert restored[1] == pytest.approx(0.25, abs=0.02)


def test_applying_mismatched_ratios_is_ignored():
    manager, _ = _make(4, is_resizable=True)
    manager._render_video_grid()

    before = manager._splitter_root.sizes()
    manager._apply_ratios(manager._splitter_root, [0.5])
    assert manager._splitter_root.sizes() == before


def test_splits_are_restored_before_the_window_is_laid_out():
    """A reopened playlist builds its splits before the window has a size.

    Every cell then reports nil, so there is no total to scale the saved
    splits against; they still have to come back, or a resize would silently
    reset them.
    """
    manager, _ = _make(4, is_resizable=True)
    manager._render_video_grid()

    # never shown, so the tree has no realised size
    assert sum(manager._splitter_rows[0].sizes()) == 0

    manager._apply_ratios(manager._splitter_rows[0], [0.75, 0.25])

    restored = manager._ratios_of(manager._splitter_rows[0])
    assert restored[0] == pytest.approx(0.75, abs=0.01)
    assert restored[1] == pytest.approx(0.25, abs=0.01)


def test_plain_grid_leaves_no_splitter_tree():
    manager, _ = _make(4, is_resizable=False)

    manager._render_video_grid()

    assert manager._splitter_root is None
    assert manager._splitter_rows == []


def test_grid_state_defaults_resizable_off():
    state = GridState()
    assert state.is_resizable is False
    assert state.splitter_sizes == []
