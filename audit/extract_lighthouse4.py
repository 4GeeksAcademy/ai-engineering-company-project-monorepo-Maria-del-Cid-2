#!/usr/bin/env python3
"""Extracción 4: detalles de las auditorías *-insight de Lighthouse 13."""
import json
import glob
import os

INSIGHTS = [
    "render-blocking-insight",
    "image-delivery-insight",
    "cache-insight",
    "lcp-discovery-insight",
    "network-dependency-tree-insight",
    "duplicated-javascript-insight",
    "third-parties-insight",
    "forced-reflow-insight",
    "legacy-javascript-insight",
    "modern-http-insight",
    "cls-culprits-insight",
    "document-latency-insight",
    "dom-size-insight",
]

for path in sorted(glob.glob("audit/json/*.json")):
    name = os.path.basename(path).replace(".json", "")
    with open(path) as f:
        d = json.load(f)
    a = d["audits"]
    print(f"\n{'='*70}\n### {name}")

    for key in INSIGHTS:
        au = a.get(key)
        if not au:
            continue
        det = au.get("details") or {}
        items = det.get("items")
        if not isinstance(items, list):
            s = json.dumps(det, ensure_ascii=False)
            if s and s != "{}":
                print(f"-- {key} score={au.get('score')} display={au.get('displayValue','')} details={s[:450]}")
            continue
        if not items and au.get("score") is None:
            continue
        print(f"-- {key} score={au.get('score')} display={au.get('displayValue','')}")
        for it in items[:8]:
            s = json.dumps(it, ensure_ascii=False)
            print(f"   {s[:450]}")

    # errores de consola
    ec = a.get("errors-in-console", {})
    for it in (ec.get("details", {}).get("items") or [])[:5]:
        print(f"-- console error: {json.dumps(it, ensure_ascii=False)[:300]}")

print("\nDONE")