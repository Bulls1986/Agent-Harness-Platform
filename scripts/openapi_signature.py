"""Stable API-signature projection, independent of FastAPI/Pydantic metadata."""
from __future__ import annotations

HTTP_METHODS=frozenset(("get","post","put","patch","delete","options","head"))
SCHEMA_KEYS=("type","format","minLength","maxLength","minimum","maximum",
             "exclusiveMinimum","exclusiveMaximum","pattern","enum","const")


def field_shape(field):
    if not isinstance(field,dict):
        return field
    result={k:field[k] for k in SCHEMA_KEYS if k in field}
    if "$ref" in field:
        result["$ref"]=field["$ref"].split("/")[-1]
    if "items" in field:
        result["items"]=field_shape(field["items"])
    if "anyOf" in field:
        result["anyOf"]=[field_shape(x) for x in field["anyOf"]]
    if "allOf" in field:
        result["allOf"]=[field_shape(x) for x in field["allOf"]]
    if "properties" in field:
        result["properties"]={k:field_shape(v)
                              for k,v in sorted(field["properties"].items())}
    if "required" in field:
        result["required"]=sorted(field["required"])
    return result


def contract_signature(document):
    """Keep routes, request/parameter shape, response codes, application models.

    Drop framework-owned examples, descriptions, validation-error component
    changes and OpenAPI renderer metadata. These vary between supported
    FastAPI/Pydantic versions without changing the application API contract.
    """
    paths={}
    for path,operations in sorted(document.get("paths",{}).items()):
        path_ops={}
        for method,op in sorted(operations.items()):
            if method not in HTTP_METHODS:
                continue
            params=sorted((
                p.get("name"),p.get("in"),bool(p.get("required",False)),
                field_shape(p.get("schema",{}))
            ) for p in op.get("parameters",[]))
            request=op.get("requestBody") or {}
            media=request.get("content",{})
            path_ops[method]={
                "parameters":params,
                "body_required":bool(request.get("required",False)),
                "body":{k:field_shape(v.get("schema",{}))
                        for k,v in sorted(media.items())},
                "response_codes":sorted(op.get("responses",{}).keys()),
            }
        paths[path]=path_ops
    models=document.get("components",{}).get("schemas",{})
    model_contract={
        name:field_shape(schema)
        for name,schema in sorted(models.items())
        if name not in {"HTTPValidationError","ValidationError"}
    }
    return {"paths":paths,"models":model_contract}