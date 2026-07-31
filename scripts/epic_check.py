#!/usr/bin/env python3
"""
epic_check.py — Xử lý epic trước khi tạo khung ticket.

Epic đổi hằng sprint -> KHÔNG hardcode. Luồng:
  1. PO nêu epic (tên hoặc key) -> tìm trong epics.json.
     - khớp key/label chính xác  -> dùng luôn.
     - khớp gần đúng             -> gợi ý PO xác nhận đúng epic nào.
     - không thấy                -> có thể là epic MỚI -> sang bước 2.
  2. Epic mới: scan TOÀN BỘ label + summary tìm khả năng trùng (fuzzy).
     - có ứng viên trùng  -> CẢNH BÁO, để PO quyết: dùng epic cũ hay vẫn tạo mới.
     - không trùng        -> OK tạo mới, PO đặt tên.

DÙNG:
  python3 epic_check.py --find "Buy Sell flow"          # tìm epic PO nêu
  python3 epic_check.py --new "Revamp Order Screen"     # scan trùng cho epic mới
  python3 epic_check.py --key PCFFS-3753                # tra theo key
"""
import sys, json, argparse
from difflib import SequenceMatcher

def load(path="epics.json"):
    return json.load(open(path, encoding="utf-8"))["epics"]

def norm(s):
    """Bỏ tag [Stock]/[FC]/[FS Hub], lowercase, gọn khoảng trắng -> so lõi ngữ nghĩa."""
    import re
    s = re.sub(r"\[[^\]]*\]", " ", s or "")
    return re.sub(r"\s+", " ", s.lower()).strip()

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def find(epics, query):
    """Tìm epic theo tên/label PO nêu."""
    q = norm(query)
    exact = [e for e in epics if norm(e["label"]) == q or norm(e["summary"]) == q]
    if exact:
        return "exact", exact
    scored = sorted(epics, key=lambda e: max(sim(query, e["label"]), sim(query, e["summary"])), reverse=True)
    top = [e for e in scored[:5] if max(sim(query, e["label"]), sim(query, e["summary"])) >= 0.5]
    return ("fuzzy", top) if top else ("none", [])

def scan_dup(epics, new_name, threshold=0.6):
    """Scan trùng cho epic mới: trả list ứng viên có độ giống >= threshold."""
    cands = []
    for e in epics:
        score = max(sim(new_name, e["label"]), sim(new_name, e["summary"]))
        if score >= threshold:
            cands.append((score, e))
    return sorted(cands, key=lambda x: -x[0])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--find"); ap.add_argument("--new"); ap.add_argument("--key")
    ap.add_argument("--epics", default="epics.json")
    a = ap.parse_args()
    epics = load(a.epics)

    if a.key:
        hit = [e for e in epics if e["key"].upper() == a.key.upper()]
        if hit:
            e = hit[0]; print(f"✓ {e['key']} · {e['label']}\n  summary: {e['summary']}")
        else:
            print(f"✗ Không có epic key {a.key}")
        return

    if a.find:
        kind, res = find(epics, a.find)
        if kind == "exact":
            e = res[0]; print(f"✓ KHỚP CHÍNH XÁC: {e['key']} · {e['label']}")
        elif kind == "fuzzy":
            print(f"⚠ Không khớp chính xác '{a.find}'. Có thể là 1 trong:")
            for e in res:
                print(f"   {e['key']} · {e['label']}  (~{sim(a.find,e['label']):.0%})")
            print("→ PO xác nhận epic đúng, hoặc dùng --new nếu là epic mới.")
        else:
            print(f"✗ Không thấy epic nào giống '{a.find}'. Có thể là epic MỚI → chạy --new.")
        return

    if a.new:
        dup = scan_dup(epics, a.new)
        if dup:
            print(f"⚠ Epic mới '{a.new}' — CÓ khả năng trùng {len(dup)} epic sẵn có:")
            for score, e in dup:
                print(f"   {score:.0%}  {e['key']} · {e['label']}")
            print("→ PO quyết: dùng lại epic cũ ở trên, hay VẪN tạo epic mới?")
        else:
            print(f"✓ '{a.new}' không trùng epic nào. OK tạo mới — PO xác nhận tên cuối.")
        return

    ap.print_help()

if __name__ == "__main__":
    main()
