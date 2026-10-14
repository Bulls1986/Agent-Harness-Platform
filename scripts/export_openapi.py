"""Export deterministic OpenAPI from actual FastAPI route factories.

The Public API uses a trusted injected authorization/PG adapter contract.
For schema emission only, bypass PgConversationStore.__init__ (no database is
opened), and NEVER serve this application as an authenticated deployment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.platform_api import create_platform_app
from poc.closed_loop.inspector import create_app


def schemas():
    # Constructor is not called: schema-only identity and store, not a runtime.
    fake_store=object.__new__(PgConversationStore)
    public=create_platform_app(
        resolve_context=lambda _request: None,
        reader=object(), store=fake_store,
        authorize=lambda *_: False,
        authorize_create=lambda *_: False,
    )
    pub=public.openapi()
    pub["paths"]={name:route for name,route in pub["paths"].items()
                  if name.startswith("/api/v1/")}
    pub["info"]["description"]=(
        "Bounded developer-facing route contract. Server-side authenticated "
        "Gateway/Policy and actual PostgreSQL adapters are required. This "
        "snapshot is not a deployed production endpoint.")
    inspector=create_app().openapi()
    inspector["info"]["description"]=(
        "Unauthenticated localhost-only Run Inspector, not a production API.")
    return {
        ROOT/"docs/api/openapi-v1.json":pub,
        ROOT/"docs/api/openapi-inspector.json":inspector,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true",
                        help="fail if checked-in schemas differ from current routes")
    args=parser.parse_args()
    ok=True
    for file,content in schemas().items():
        rendered=json.dumps(content,indent=2,ensure_ascii=False,sort_keys=True)+"\n"
        if args.check:
            if not file.is_file() or file.read_text(encoding="utf-8")!=rendered:
                print("STALE OpenAPI snapshot:",file.relative_to(ROOT))
                ok=False
        else:
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(rendered,encoding="utf-8")
            print("exported",file.relative_to(ROOT))
    return 0 if ok else 1


if __name__=="__main__":
    raise SystemExit(main())