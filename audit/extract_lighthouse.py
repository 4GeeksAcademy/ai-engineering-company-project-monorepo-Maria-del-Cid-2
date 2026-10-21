#!/usr/bin/env python3
"""Extrae datos clave de los JSON de Lighthouse en audit/json/."""
import json
import glob
import os

METRICS = [
    ("first-contentful-paint", "FCP"),
    ("largest-contentful-paint", "LCP"),
    ("total-blocking-time", "TBT"),
    ("cumulative-layout-shift", "CLS"),
    ("speed-index", "SI"),
    ("time-to-first-byte", "TTFB"),
    ("interactive", "TTI"),
]

DIAGNOSTICS = [
    "uses-optimized-images",
    "uses-responsive-images",
    "render-blocking-resources",
    "total-byte-weight",
    "dom-size",
    "mainthread-work-breakdown",
    "long-tasks",
    "uses-long-cache-ttl",
    "unminified-css",
    "unminified-javascript",
    "unused-css-rules",
    "unused-javascript",
    "font-display",
    "layout-shifts",
]

FILES = sorted(glob.glob("audit/json/*.json"))


def ms(v):
    if v is None:
        return "—"
    if v >= 1000:
        return f"{v/1000:.1f}s"
    return f"{round(v)}ms"


def kb(v):
    if v is None:
        return "—"
    if v >= 1024 * 1024:
        return f"{v/1024/1024:.1f} MB"
    return f"{round(v/1024)} KiB"


for path in FILES:
    name = os.path.basename(path).replace(".json", "")
    with open(path) as f:
        d = json.load(f)

    print(f"\n{'='*70}")
    print(f"### {name}  (URL: {d.get('finalDisplayedUrl', d.get('finalUrl','?'))})")
    devtools = d.get("configSettings", {})
    print(f"    emulación: formFactor={devtools.get('formFactor')} "
          f"throttling={devtools.get('throttlingMethod')}")

    print("  Scores:", " | ".join(
        f"{c['id']}={round(c['score']*100)}" for c in d["categories"].values()))

    audits = d["audits"]
    print("  Métricas:")
    for aid, label in METRICS:
        a = audits.get(aid)
        if a and a.get("numericValue") is not None:
            print(f"    {label:6} {ms(a['numericValue']):>8}  (score={a.get('score')})")

    # LCP element
    lcp = audits.get("largest-contentful-paint-element", {})
    elems = lcp.get("details", {}).get("items", [])
    for it in elems:
        node = it.get("node") or {}
        if node:
            print(f"  LCP element: {node.get('selector','?')[:160]}")
            print(f"    snippet: {(node.get('snippet') or '')[:220]}")

    print("  Diagnósticos (con ahorro/situación):")
    for aid in DIAGNOSTICS:
        a = audits.get(aid)
        if not a:
            continue
        score = a.get("score")
        if score is None and not a.get("details"):
            continue
        status = "❌" if score == 0 else ("✓" if score == 1 else "~")
        title = a.get("title", aid)
        display = a.get("displayValue", "")
        line = f"    {status} {aid}: {title[:60]} {display}"
        # savings
        det = a.get("details") or {}
        overall = det.get("overallSavingsMs")
        if overall:
            line += f" (ahorro≈{ms(overall)})"
        ovb = det.get("overallSavingsBytes")
        if ovb:
            line += f" {kb(ovb)}"
        if aid == "total-byte-weight":
            line = f"    {status} {aid}: {display}"
        if aid == "dom-size":
            line = f"    {status} {aid}: {display}"
        print(line)
        # render-blocking: listar recursos
        if aid == "render-blocking-resources":
            for it in (det.get("items") or [])[:6]:
                print(f"        - {it.get('url','')[:100]} {ms(it.get('wastedMs'))} "
                      f"({it.get('totalBytes','?')}B) [{it.get('resourceType','')} {'cache=' + str(it.get('cacheHit')) if it.get('cacheHit') is not None else ''}]")
        if aid == "long-tasks":
            for it in (det.get("items") or [])[:8]:
                print(f"        - {ms(it.get('duration'))} en {it.get('startTime','?')}ms  "
                      f"{(it.get('url') or it.get('frame') or '?')[:80]}")
        if aid == "mainthread-work-breakdown":
            for it in (det.get("items") or [])[:6]:
                print(f"        - {it.get('groupLabel','?')}: {ms(it.get('duration'))}")
        if aid in ("uses-optimized-images", "uses-responsive-images", "unused-javascript", "unused-css-rules"):
            total = sum(it.get("totalBytes", 0) for it in (det.get("items") or []))
            print(f"        (bytes implicados: {kb(total)}, {len(det.get('items') or [])} recursos)")

    # network requests: top by size
    net = audits.get("network-requests", {})
    items = sorted(net.get("details", {}).get("items", []),
                   key=lambda x: -(x.get("transferSize") or 0))[:12]
    if items:
        print("  Top transferencias:")
        for it in items:
            print(f"    {kb(it.get('transferSize')):>9}  {it.get('resourceType','?'):12} "
                  f"{it.get('url','')[:110]}")

    # third-party summary
    tp = audits.get("third-party-summary", {})
    if tp.get("details", {}).get("items"):
        print("  Third-party:")
        for it in tp["details"]["items"][:6]:
            print(f"    {it.get('entity','?')[:60]}: bloqueo={ms(it.get('blockingTime'))} "
                  f"bytes={kb(it.get('transferSize'))}")

    # LCP breakdown (lantern)
    lcpb = audits.get("lcp-lazy-loaded") or audits.get("prioritize-lcp-image") or {}
    pli = audits.get("prioritize-lcp-image")
    if pli and pli.get("score") is not None:
        print(f"  prioritize-lcp-image: score={pli.get('score')} {pli.get('displayValue','')}")

    # opportunities: largest wasted
    print("  Oportunidades ordenadas (ahorro potencial):")
    opps = []
    for aid, a in audits.items():
        if a.get("score") is None and a.get("scoreDisplayMode") in ("numeric", "binary", "metricSavings"):
            pass
        if a.get("scoreDisplayMode") == "informative" and a.get("details", {}).get("overallSavingsMs"):
            opps.append((a["details"]["overallSavingsMs"], aid, a.get("displayValue", "")))
    opps.sort(reverse=True)
    for sav, aid, disp in opps[:8]:
        print(f"    {ms(sav):>8}  {aid}  {disp}")

print("\nDONE")