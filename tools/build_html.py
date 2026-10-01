"""Build web/sanguine.html: a single self-contained page (the geocities-goth port).

    python tools/build_html.py

Content comes from the same TOML files the terminal game uses, embedded as JSON into web/template.html.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, ".")
from sanguine.engine.content import load_content  # noqa: E402

c = load_content()
data = dict(ventures=[asdict(v) for v in c.ventures], milestones=[asdict(m) for m in c.milestones],
            global_milestones=[asdict(m) for m in c.global_milestones], upgrades=[asdict(u) for u in c.upgrades],
            events=c.events, dossiers=c.dossiers, branches=c.branches, nodes=c.nodes, headlines=c.headlines)
tpl = Path("web/template.html").read_text()
out = tpl.replace("/*CONTENT*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
Path("web/sanguine.html").write_text(out)
print(f"web/sanguine.html: {len(out) / 1024:.0f} KiB")
