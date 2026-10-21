#!/usr/bin/env python3
"""Extracción 3: desglose LCP por subpartes + render-blocking + auditorías 'insight'."""
import json
import glob
import os

for path in sorted(glob.glob("audit/json/*.json")):
    name = os.path.basename(path).replace(".json", "")
    with open(path) as f:
        d = json.load(f)
    a = d["audits"]
    print(f"\n{'='*70}\n### {name}")

    # LCP breakdown completo
    lb = a.get("lcp-breakdown-insight", {})
    det = lb.get("details") or {}
    for it in det.get("items") or []:
        if it.get("type") == "table":
            for row in it.get("items") or []:
                print(f"  LCP subpart {row.get('subpart','?')}: {row.get('duration','?'):.1f}ms ({row.get('label','')})")
        elif it.get("type") == "node":
            print(f"  LCP node: {it.get('selector','')}")
            sn = (it.get("snippet") or "").replace("\n", " ")
            print(f"  snippet: {sn[:400]}")

    # subpartes guardadas en metricSavings / details alternativos
    lcp_au = a.get("largest-contentful-paint", {})
    print(f"  LCP numericValue={lcp_au.get('numericValue')}")
    ms_ = lcp_au.get("metricSavings")
    if ms_:
        print(f"  metricSavings: {json.dumps(ms_, ensure_ascii=False)}")

    # render-blocking completo
    rb = a.get("render-blocking-resources", {})
    print(f"  render-blocking: score={rb.get('score')} display={rb.get('displayValue')} "
          f"desc={rb.get('description','')[:120]}")
    rbd = rb.get("details") or {}
    print(f"  rb details keys: {list(rbd.keys())} items={len(rbd.get('items') or [])}")
    for it in (rbd.get("items") or [])[:8]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:400]}")

    # todas las auditorías con 'insight' o que fallen (score 0)
    print("  Auditorías con score=0 (fallidas):")
    for aid, au in sorted(a.items()):
        if au.get("score") == 0:
            print(f"    ❌ {aid}: {au.get('title','')[:70]} {au.get('displayValue','')}")

    # insight keys presentes
    insights = [k for k in a if "insight" in k]
    print(f"  insight audits: {insights}")

    # third-party raw
    tp = a.get("third-party-summary", {})
    print(f"  third-party raw: score={tp.get('score')} items={len((tp.get('details') or {}).get('items') or [])} display={tp.get('displayValue')}")
    for it in (tp.get("details", {}).get("items") or [])[:6]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:300]}")

    # wastedMs en algún audit de render-blocking fonts
    fd = a.get("font-display", {})
    print(f"  font-display: score={fd.get('score')} items={len((fd.get('details') or {}).get('items') or [])} display={fd.get('displayValue')}")

    # opportunities de ahorro (Lighthouse 13 puede usar metricSavings en audit-level)
    opp_keys = ("render-blocking-resources", "unused-javascript", "unused-css-rules",
                "uses-optimized-images", "uses-responsive-images", "modern-image-formats",
                "offscreen-images", "unminified-javascript", "unminified-css",
                "uses-long-cache-ttl", "uses-http2", "total-byte-weight")
    print("  savings (overallSavingsMs/Bytes):")
    for k in opp_keys:
        au = a.get(k)
        if not au:
            continue
        dd = au.get("details") or {}
        if dd.get("overallSavingsMs") or dd.get("overallSavingsBytes"):
            print(f"    {k}: {ms_ if False else ''} "
                  f"ms={dd.get('overallSavingsMs')} bytes={dd.get('overallSavingsBytes')} "
                  f"items={len(dd.get('items') or [])}")

print("\nDONE")