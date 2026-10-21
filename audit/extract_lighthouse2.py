#!/usr/bin/env python3
"""Volcado detallado: LCP element, render-blocking, imágenes, layout-shifts, third-party."""
import json
import glob
import os

for path in sorted(glob.glob("audit/json/*.json")):
    name = os.path.basename(path).replace(".json", "")
    with open(path) as f:
        d = json.load(f)
    a = d["audits"]
    print(f"\n{'='*70}\n### {name}")

    # 1. LCP element
    for key in ("largest-contentful-paint-element", "lcp-lazy-loaded",
                "prioritize-lcp-image", "lcp-breakdown-insight"):
        if key in a:
            det = a[key].get("details")
            print(f"-- {key}: score={a[key].get('score')} display={a[key].get('displayValue')}")
            if det:
                for it in (det.get("items") or [])[:6]:
                    node = it.get("node") or {}
                    if node:
                        print(f"   node: {node.get('selector','')[:180]}")
                        print(f"   snippet: {(node.get('snippet') or '')[:260]}")
                    else:
                        # metricSavings o items simples
                        slim = {k: v for k, v in it.items() if k not in ("node",)}
                        print(f"   item: {json.dumps(slim, ensure_ascii=False)[:300]}")

    # metricSavings (Lighthouse 13 guarda ahorros por métrica)
    ms_ = a.get("largest-contentful-paint", {}).get("metricSavings") or {}
    if ms_:
        print(f"-- LCP metricSavings: {json.dumps(ms_, ensure_ascii=False)[:400]}")

    # 2. render-blocking
    rb = a.get("render-blocking-resources", {})
    print(f"-- render-blocking: score={rb.get('score')} display={rb.get('displayValue')}")
    for it in (rb.get("details", {}).get("items") or [])[:8]:
        print(f"   {it.get('resourceType','?'):10} {it.get('totalBytes','?'):>7}B "
              f"wastedMs={it.get('wastedMs')} cache={it.get('cacheHit')} "
              f"{it.get('url','')[:110]}")

    # 3. imágenes
    for key in ("uses-optimized-images", "uses-responsive-images",
                "offscreen-images", "modern-image-formats", "image-size-responsive"):
        if key not in a:
            continue
        au = a[key]
        det = au.get("details") or {}
        items = det.get("items") or []
        print(f"-- {key}: score={au.get('score')} display={au.get('displayValue','')} "
              f"overallSavingsBytes={det.get('overallSavingsBytes')} items={len(items)}")
        for it in items[:6]:
            print(f"   {json.dumps(it, ensure_ascii=False)[:280]}")

    # 4. layout-shifts
    ls = a.get("layout-shifts", {})
    det = ls.get("details") or {}
    print(f"-- layout-shifts: score={ls.get('score')} display={ls.get('displayValue','')}")
    for it in (det.get("items") or [])[:5]:
        print(f"   {json.dumps(it, ensure_ascii=False)[:280]}")

    # 5. third-party
    tp = a.get("third-party-summary", {})
    print(f"-- third-party: score={tp.get('score')} display={tp.get('displayValue','')}")
    for it in (tp.get("details", {}).get("items") or [])[:8]:
        print(f"   {json.dumps(it, ensure_ascii=False)[:280]}")

    # 6. unused-javascript items
    uj = a.get("unused-javascript", {})
    for it in (uj.get("details", {}).get("items") or [])[:5]:
        print(f"-- unused-js: {json.dumps(it, ensure_ascii=False)[:280]}")

    # 7. network-requests: buscar unsplash / tailwind / location-catalog / logo
    net = a.get("network-requests", {}).get("details", {}).get("items") or []
    print("-- network (clave):")
    for it in net:
        u = it.get("url", "")
        if any(k in u for k in ("unsplash", "tailwind", "location-catalog", "Logo", "map", "validation")):
            print(f"   {it.get('resourceType','?'):10} proto={it.get('protocol','?')} "
                  f"status={it.get('statusCode')} transfer={it.get('transferSize')} "
                  f"resource={it.get('resourceSize')} startTime={round(it.get('startTime',0))}ms "
                  f"{u[:100]}")

    # 8. font-display
    fd = a.get("font-display", {})
    print(f"-- font-display: score={fd.get('score')} display={fd.get('displayValue','')} "
          f"items={len((fd.get('details') or {}).get('items') or [])}")

    # 9. mainthread breakdown items completos
    mt = a.get("mainthread-work-breakdown", {})
    print(f"-- mainthread: display={mt.get('displayValue')}")
    for it in (mt.get("details", {}).get("items") or [])[:8]:
        print(f"   {it.get('group','?'):24} {it.get('duration','?')}ms")

    # 10. diagnostics: scripts / images savings
    for key in ("bootup-time", "font-size", "uses-passive-event-listeners",
                "insight-uses-responsive-images", "insight-modern-image-formats"):
        if key in a and a[key].get("displayValue"):
            print(f"-- {key}: {a[key].get('displayValue')}")

    # 11. final url / fetchpriority presence via critical-request-chains
    crc = a.get("critical-request-chains", {})
    print(f"-- critical-request-chains: display={crc.get('displayValue','')}")

print("\nDONE")