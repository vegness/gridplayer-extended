from PyQt5.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QSplitter, QSplitterHandle

from gridplayer.widgets.cell_chrome import chrome_color

# How thick a handle is to hit, and how thick the line it draws is. The
# handle is as wide as a comfortable mouse target and the line inside it is
# a hairline, so the grid reads as cells butted together with a seam.
HANDLE_WIDTH = 8
HANDLE_LINE = 2


class GridSplitterHandle(QSplitterHandle):
    """A handle drawn as a thin seam, which a double click resets.

    QSplitter's own handle is a plain grey bar. This one draws a hairline in
    the cell chrome's colour, so the grid keeps its look, and grows the mouse
    target around it.
    """

    double_clicked = pyqtSignal()

    def __init__(self, orientation, parent, **kwargs):
        super().__init__(orientation, parent, **kwargs)

        self.setAttribute(Qt.WA_StyledBackground, False)
        self._is_hovered = False
        self.setMouseTracking(True)

    def sizeHint(self):
        return self._handle_size()

    def _handle_size(self):
        if self.orientation() == Qt.Horizontal:
            return (
                super()
                .sizeHint()
                .expandedTo(self.parent()._handle_size_for(Qt.Horizontal))
            )
        return (
            super().sizeHint().expandedTo(self.parent()._handle_size_for(Qt.Vertical))
        )

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = chrome_color(self)
        if self._is_hovered:
            color = chrome_color(self, alpha=200)

        pen = QPen(color)
        pen.setWidthF(HANDLE_LINE)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        rect = QRectF(self.rect())
        if self.orientation() == Qt.Horizontal:
            x = rect.center().x()
            painter.drawLine(
                int(x),
                int(rect.top() + HANDLE_WIDTH / 2),
                int(x),
                int(rect.bottom() - HANDLE_WIDTH / 2),
            )
        else:
            y = rect.center().y()
            painter.drawLine(
                int(rect.left() + HANDLE_WIDTH / 2),
                int(y),
                int(rect.right() - HANDLE_WIDTH / 2),
                int(y),
            )

        painter.end()


class GridSplitter(QSplitter):
    """A splitter between cells of the grid, with a thin drawn handle.

    Used one per row and one per column, nested, so a drag on one seam
    resizes the cells either side of it and leaves the rest alone -- the way
    a desktop's own window tiling behaves.
    """

    layout_changed = pyqtSignal()

    def __init__(self, orientation, **kwargs):
        super().__init__(orientation, **kwargs)

        self.setChildrenCollapsible(False)
        self.setHandleWidth(HANDLE_WIDTH)
        self.setOpaqueResize(True)

        self.splitterMoved.connect(lambda *_: self.layout_changed.emit())

    def createHandle(self):
        handle = GridSplitterHandle(self.orientation(), self)
        handle.double_clicked.connect(self._reset_even)
        return handle

    def _handle_size_for(self, orientation):
        if orientation == Qt.Horizontal:
            return QSize(HANDLE_WIDTH, 0)
        return QSize(0, HANDLE_WIDTH)

    def _reset_even(self):
        """Put the seam back in the middle of the cells it divides."""
        count = self.count()
        if count < 2:
            return

        total = sum(self.sizes())
        if total <= 0:
            return

        even = total // count
        sizes = [even] * count
        sizes[-1] += total - even * count
        self.setSizes(sizes)
