#!/usr/bin/env python3
"""
check_schema.py — Kiểm 1 file trung gian (do BẤT KỲ parser nào sinh ra) có đủ
schema để tạo Jira ticket không, và in bảng cho PO hiểu.

Ý tưởng: skill KHÔNG quan tâm source là PRD/FigJam/Notion/gì.
Mọi parser phải xuất ra cùng 1 schema JSON (list story). Script này là "cửa kiểm":
  - đủ field bắt buộc  → OK, sẵn sàng enrich + tạo ticket
  - thiếu              → chỉ rõ story nào thiếu field gì

DÙNG:
  python3 check_schema.py stories.json
  python3 check_schema.py --show-schema      # chỉ in bảng schema, không cần file
"""
import sys, json, argparse

# ---- ĐỊNH NGHĨA SCHEMA TRUNG GIAN (hợp đồng chung mọi parser tuân theo) ----
SOURCE_FIELDS = [
    # (field,        bắt buộc, mô tả)
    ("summary",      True,  "Tên story"),
    ("description",  True,  "User story + acceptance criteria"),
    ("us_id",        False, "Mã US (US-01…) để nhóm & idempotent"),
    ("subtasks",     False, "List sub-task; chỉ tạo nếu source có"),
    ("assignee",     False, "Username người làm (field mềm)"),
    ("points",       False, "Story point (field mềm)"),
]
KNOWLEDGE_FIELDS = [
    ("project_key",    "PCFFS"),
    ("workstream",     "dropdown — từ config"),
    ("product_domain", "dropdown — từ config"),
    ("sub_domain",     "dropdown — từ config"),
    ("epic",           "epic link key — từ config"),
    ("reporter",       "từ config"),
    ("field ID + format", "map customfield + {value}/text — từ config"),
]

def show_schema():
    print("\n╭─ SCHEMA TẠO TICKET ─────────────────────────────────────────╮")
    print("│ SOURCE phải cung cấp (PRD / FigJam / bất kỳ):               │")
    print("├──────────────┬────────────┬─────────────────────────────────┤")
    print(f"│ {'FIELD':<12} │ {'BẮT BUỘC':<10} │ {'Ý NGHĨA':<31} │")
    print("├──────────────┼────────────┼─────────────────────────────────┤")
    for f, req, desc in SOURCE_FIELDS:
        print(f"│ {f:<12} │ {'✅ có' if req else '– tuỳ':<10} │ {desc:<31} │")
    print("├──────────────┴────────────┴─────────────────────────────────┤")
    print("│ KNOWLEDGE tự fill (không cần source — từ jira_config.json): │")
    print("├────────────────────────┬─────────────────────────────────────┤")
    for f, src in KNOWLEDGE_FIELDS:
        print(f"│ {f:<22} │ {src:<35} │")
    print("╰────────────────────────┴─────────────────────────────────────╯")
    print("\n→ Skill chỉ cần source đắp đủ nhóm BẮT BUỘC. Còn lại máy tự lo.\n")

def check(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"✗ Không đọc được {path}: {e}")
    if isinstance(data, dict):
        data = [data]
    required = [f for f, req, _ in SOURCE_FIELDS if req]

    ok, problems = 0, []
    for i, story in enumerate(data):
        miss = [f for f in required if not story.get(f)]
        label = story.get("us_id") or story.get("summary", f"#{i+1}")[:30]
        if miss:
            problems.append(f"  ✗ {label}: thiếu {', '.join(miss)}")
        else:
            ok += 1

    print(f"\nKiểm {len(data)} story: {ok} đủ schema, {len(problems)} thiếu.")
    if problems:
        print("\n".join(problems))
        print("\n→ Source chưa đủ. Bổ sung field thiếu vào source rồi parse lại.")
        sys.exit(1)
    print("✓ Tất cả story đủ schema bắt buộc. Sẵn sàng enrich + tạo ticket.\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--show-schema", action="store_true")
    a = ap.parse_args()
    if a.show_schema or not a.file:
        show_schema()
    else:
        check(a.file)
