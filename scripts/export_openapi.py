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
from scripts.openapi_signature import contract_signature
from poc.sandbox.sbx_api import create_sbx_m1_app
from poc.sandbox.sbx_management import CubeNativeCreateTransport, SandboxCreateService
from poc.sandbox.sbx_template import CubeTemplateGateway
from poc.sandbox.sbx_attach import SessionAttachService, PgSessionBindingStore


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
    # M1-only API: schema-only adapters, no native Cube or database I/O.
    sbx = create_sbx_m1_app(
        resolve_context=lambda _request: None,
        service=SandboxCreateService(
            object(), CubeNativeCreateTransport(sdk=object()),
            authorize=lambda *_: False,
        ),
        template_gateway=CubeTemplateGateway(
            sdk=object(), authorize=lambda *_: False),
    ).openapi()
    sbx["info"]["description"] = (
        "DEV-SBX M1 Create/onCreate pilot only. Requires trusted Gateway,"
        " explicit Policy and PostgreSQL; no Cube/PG is contacted by this exporter."
        " Native Cube Template admin is separately Policy-gated."
        " Not a deployed production endpoint, Attach/Execute not yet implemented.")
    # M2 schema-only binding adapter. No PostgreSQL / Cube / Policy calls.
    class NeverConnect:
        def connect(self, sandbox_id):
            raise RuntimeError("OpenAPI-only adapter must never execute")
    schema_binding = SessionAttachService(
        store=object.__new__(PgSessionBindingStore),
        create_store=object(),native=NeverConnect(),
        authorize=lambda *_: False,authorize_session=lambda *_: False)
    sbx_m2=create_sbx_m1_app(
        resolve_context=lambda _request:None,
        service=SandboxCreateService(
            object(),CubeNativeCreateTransport(sdk=object()),
            authorize=lambda *_:False),
        template_gateway=CubeTemplateGateway(
            sdk=object(),authorize=lambda *_:False),
        attach_service=schema_binding,
    ).openapi()
    sbx_m2["info"]["description"]=(
        "DEV-SBX M2 bounded API: native Cube Create + Session Attach/onAttach, "
        "read/reconnect and fail-closed operator reconciliation. "
        "Gateway Session identity, Policy, short-lived InitializationPermit "
        "and real PostgreSQL must be injected on actual deployment. "
        "No Run Execute or production authentication is provided.")
    return {
        ROOT/"docs/api/openapi-sbx-m2.json":sbx_m2,
        ROOT/"docs/api/openapi-sbx-m1.json":sbx,
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
            if not file.is_file():
                print("MISSING OpenAPI snapshot:",file.relative_to(ROOT))
                ok=False
            else:
                checked=json.loads(file.read_text(encoding="utf-8"))
                if contract_signature(checked)!=contract_signature(content):
                    print("API CONTRACT DRIFT:",file.relative_to(ROOT))
                    ok=False
                elif file.read_text(encoding="utf-8")!=rendered:
                    print("Framework-only OpenAPI metadata drift (allowed):",
                          file.relative_to(ROOT))
        else:
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(rendered,encoding="utf-8")
            print("exported",file.relative_to(ROOT))
    return 0 if ok else 1


if __name__=="__main__":
    raise SystemExit(main())