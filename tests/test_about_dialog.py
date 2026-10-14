"""The About dialog has to say where this build came from.

This is not decoration. The GPL asks a modified copy to keep the notices of
the work it was made from, and this dialog is the only place a user of the
built program ever sees them. Losing that line is a licensing problem, not a
cosmetic one, so it is worth a test.
"""

import pytest
from PyQt5.QtWidgets import QApplication, QWidget

from gridplayer.dialogs.about import AboutDialog
from gridplayer.version import (
    __app_bugtracker_url__,
    __app_url__,
    __display_name__,
    __fork_author__,
    __upstream_author__,
    __upstream_url__,
)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def about_window():
    """The dialog, built once, with a parent to keep it alive."""

    parent = QWidget()
    dialog = AboutDialog(parent)

    yield dialog

    dialog.close()
    parent.close()


def _info(about_window):
    return about_window.info.text()


def _attributions_html(about_window):
    box = about_window.attributionsBox
    return box.toHtml() + box.toPlainText()


@pytest.mark.parametrize(
    "template_vars",
    [
        "{APP_URL}",
        "{APP_BUGTRACKER_URL}",
        "{APP_LICENSE_URL}",
        "{UPSTREAM_URL}",
        "{UPSTREAM_AUTHOR}",
        "{FORK_AUTHOR}",
        "{APP_DISP_NAME}",
    ],
)
def test_no_placeholder_is_left_unsubstituted(about_window, template_vars):
    assert template_vars not in _info(about_window)


def test_it_says_this_is_a_modified_copy(about_window):
    assert "modified copy" in _info(about_window)


def test_it_names_the_work_it_is_based_on(about_window):
    info = _info(about_window)

    assert __upstream_url__ in info
    assert __upstream_author__ in info


def test_it_names_where_this_build_comes_from(about_window):
    info = _info(about_window)

    assert __app_url__ in info
    assert __fork_author__ in info


def test_bug_reports_go_to_this_build_not_upstream(about_window):
    assert __app_bugtracker_url__ in _info(about_window)


def test_the_display_name_is_still_the_program_name(about_window):
    assert about_window.name.text() == __display_name__


def test_the_original_work_is_credited_among_the_attributions(about_window):
    """The one credit the license does not let slide, in the list where
    a user would look for it."""

    attributions = _attributions_html(about_window)

    assert __upstream_url__ in attributions
    assert __upstream_author__ in attributions


def test_the_upstream_is_not_passed_off_as_this_fork(about_window):
    """Two different repositories, told apart, not one link to rule them."""

    attributions = _attributions_html(about_window)

    assert __upstream_url__ != __app_url__
    assert __upstream_url__ in attributions
