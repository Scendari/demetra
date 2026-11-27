"""La page /guide/ : le Markdown du mode d'emploi rendu en HTML, listes numérotées et blocs de code
compris."""

from __future__ import annotations

import re

import pytest

from core import guide


def test_a_code_block_inside_a_numbered_step_stays_in_its_step():
    html = guide.to_html(
        "1. **Demandez** :\n\n   ```bash\n   curl -X POST <url>\n   ```\n\n   Puis lisez.\n\n2. Ensuite.\n"
    )
    assert html.count("<ol>") == 1 and html.count("<li>") == 2
    assert '<pre><code class="language-bash">curl -X POST &lt;url&gt;\n</code></pre>' in html
    assert html.index("<pre>") < html.index("</li>") and "```" not in html


@pytest.mark.django_db
def test_the_agents_page_keeps_its_steps_and_commands(client):
    html = client.get("/guide/agents/").content.decode()
    first = re.search(r"<ol>(.*?)</ol>", html, flags=re.DOTALL).group(1)
    assert first.count("<pre>") == 3 and "Vérifiez" in first
    assert '<code class="language-bash">curl -sS -X POST' in first
    assert "```" not in html and "DEMETRA-CODE" not in html


@pytest.mark.django_db
@pytest.mark.parametrize("topic", list(guide.TOPICS))
def test_no_topic_leaves_a_fence_or_a_mark_behind(client, topic):
    html = client.get(f"/guide/{topic}/").content.decode()
    assert "```" not in html and "DEMETRA-CODE" not in html
