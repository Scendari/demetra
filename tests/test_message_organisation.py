"""Message de l'organisation : ce que l'administrateur ajoute au mode d'emploi depuis /admin/."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core import guide
from core.models import AuditEvent, SiteNotice

from .conftest import PASSWORD

MESSAGE = "Demetra est l'outil validé par la DSI.\nContact : équipe <outils>."
LINES = (
    "Demetra (ce site) est validé pour recevoir les cas tirés de ce code.\n\n"
    "- Ne déposer que des cas anonymisés."
)


@pytest.fixture
def admin_client(db):
    get_user_model().objects.create_superuser("chef", "chef@example.org", PASSWORD)
    client = Client()
    assert client.login(username="chef", password=PASSWORD)
    return client


@pytest.fixture
def notice(db):
    return SiteNotice.objects.create(pk=1, message=MESSAGE, project_lines=LINES)


def test_without_a_notice_the_guide_is_the_written_text(db):
    for topic in guide.TOPICS:
        written = guide._read(topic)
        assert guide.markdown(topic, "https://x") == written.replace("{{origin}}", "https://x").replace(
            "{{version}}", guide.settings.DEMETRA_GUIDE_VERSION
        )
    assert "Message de l'administrateur" not in guide.llms_txt("https://x")


def test_the_message_heads_llms_txt_and_the_first_chapters(notice, client):
    llms = client.get("/llms.txt").content.decode()
    assert "**Message de l'administrateur de ce site**\n\n> Demetra est l'outil validé par la DSI." in llms
    assert "> Contact : équipe <outils>." in llms
    for topic in guide.NOTICE_TOPICS:
        text = guide.markdown(topic, "https://x")
        version_line = text.index("Version ")
        assert version_line < text.index("> Demetra est l'outil validé") < text.index("\n## ")
    assert "Demetra est l'outil validé" not in guide.markdown("cases", "https://x")


def test_the_project_lines_close_the_block_to_copy(notice, client):
    text = client.get("/api/v1/guide/agents?format=md").content.decode()
    block = text.split("```markdown\n", 1)[1].split("```", 1)[0]
    assert block.endswith(
        "guide?format=md.\n"
        "- Demetra (ce site) est validé pour recevoir les cas tirés de ce code.\n"
        "- Ne déposer que des cas anonymisés.\n"
    )


def test_a_line_cannot_close_the_block():
    assert guide.project_lines("fin ``` puis\n  \n") == ["- fin ` ` ` puis"]


def test_the_guide_page_escapes_the_message(notice, client):
    page = client.get("/guide/").content.decode()
    assert "équipe &lt;outils&gt;." in page
    assert "<outils>" not in page


def test_the_admin_edits_the_single_notice_and_it_is_journaled(admin_client):
    assert admin_client.get("/admin/core/sitenotice/").url == "/admin/core/sitenotice/add/"
    response = admin_client.post("/admin/core/sitenotice/add/", {"message": "Bonjour", "project_lines": ""})
    assert response.status_code == 302
    notice = SiteNotice.current()
    assert notice.pk == 1 and notice.updated_by.username == "chef"
    assert admin_client.get("/admin/core/sitenotice/").url == "/admin/core/sitenotice/1/change/"
    assert admin_client.get("/admin/core/sitenotice/add/").status_code == 403
    assert admin_client.get("/admin/core/sitenotice/1/change/").status_code == 200
    event = AuditEvent.objects.get(action="site_notice.updated")
    assert event.channel == "admin" and event.study is None and event.detail["fields"] == ["message"]
    assert "Bonjour" in admin_client.get("/llms.txt").content.decode()
