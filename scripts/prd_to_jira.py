#!/usr/bin/env python3
"""
prd_to_jira.py — Đọc PRD (HTML) -> tạo Story (+ Sub-task nếu có) trên Jira DC.

AUTH: Bearer PAT (giống hệt cách bạn đã đẩy PRD lên Confluence).
CONFIG: đọc field mặc định + field ID từ jira_config.json (PO maintain).
AN TOÀN: mặc định DRY-RUN. Token đọc từ env JIRA_TOKEN.

DÙNG:
  export JIRA_TOKEN='<PAT>'
  export JIRA_DOMAIN='https://jira.zalopay.vn'

  # Xem trước (không ghi Jira):
  python3 prd_to_jira.py --prd PCFFS-21886_PRD_review.html

  # Tạo thật:
  python3 prd_to_jira.py --prd PCFFS-21886_PRD_review.html --create

  # Dò field ID (điền vào jira_config.json):
  python3 prd_to_jira.py --list-fields
"""
import os, re, sys, json, argparse, ssl, urllib.request, urllib.error
from datetime import date, timedelta
from html.parser import HTMLParser

JIRA_TOKEN  = os.environ.get("JIRA_TOKEN", "")
JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN", "https://jira.zalopay.vn").rstrip("/")
JIRA_API    = "2"
SSL_CTX     = None   # set trong main(): None = verify bình thường; unverified nếu --insecure

def load_config(path="jira_config.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ---------------- HTTP ----------------
def _req(url, method="GET", body=None):
    if not JIRA_TOKEN:
        sys.exit("Thiếu JIRA_TOKEN. export JIRA_TOKEN='<PAT>'")
    data = json.dumps(body).encode() if body is not None else None
    h = {"Authorization": f"Bearer {JIRA_TOKEN}",
         "Content-Type": "application/json", "Accept": "application/json"}
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30, context=SSL_CTX) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")

def list_fields():
    st, data = _req(f"{JIRA_DOMAIN}/rest/api/{JIRA_API}/field")
    if st != 200:
        sys.exit(f"Lỗi {st}: {data}")
    print(f"{'ID':<24}NAME")
    for f in sorted(data, key=lambda x: x.get("name","")):
        if f.get("id","").startswith("customfield_") or f.get("name","").lower() in (
            "story points","sprint","epic link","parent"):
            print(f"{f['id']:<24}{f.get('name','')}")

def inspect(issue_key):
    """Đọc 1 ticket thật -> map name->id + format value. Cách chắc nhất để điền field_ids."""
    st, meta = _req(f"{JIRA_DOMAIN}/rest/api/{JIRA_API}/field")
    if st != 200: sys.exit(f"/field lỗi {st}: {meta}")
    id2name = {f["id"]: f.get("name","") for f in meta}

    st, data = _req(f"{JIRA_DOMAIN}/rest/api/{JIRA_API}/issue/{issue_key}")
    if st != 200: sys.exit(f"Đọc {issue_key} lỗi {st}: {data}")
    fields = data.get("fields", {})

    print(f"\n=== Field CÓ GIÁ TRỊ trong {issue_key} (dùng để điền jira_config) ===\n")
    print(f"{'FIELD ID':<24}{'TÊN':<28}FORMAT / GIÁ TRỊ MẪU")
    print("-"*90)
    for fid, val in fields.items():
        if val is None or val == [] or val == "": continue
        name = id2name.get(fid, "")
        if isinstance(val, dict):
            keys = list(val.keys())
            fmt = "{"+", ".join(k for k in keys if k in ("value","id","name","key"))+"}"
            sample = val.get("value") or val.get("name") or val.get("key") or ""
            shown = f'dropdown {fmt}  -> "{sample}"'
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            shown = f"array[dict] keys={list(val[0].keys())[:4]}"
        else:
            shown = str(val)[:50]
        # chỉ in customfield + vài field chuẩn hay dùng
        if fid.startswith("customfield_") or fid in (
            "summary","assignee","reporter","issuetype","description","priority"):
            print(f"{fid:<24}{name[:26]:<28}{shown}")
    print("\n-> Copy customfield ID tương ứng (Story Points, Workstream, "
          "Product Domain, Sub Domain, Sprint, Epic) vào jira_config.json > field_ids")

# ---------------- Parse PRD HTML ----------------
class PRDParser(HTMLParser):
    """Rút heading US + đoạn text kế tiếp làm description thô."""
    def __init__(self):
        super().__init__()
        self.blocks = []          # (tag, text)
        self._tag = None
        self._buf = ""
    def handle_starttag(self, tag, attrs):
        if tag in ("h1","h2","h3","li","p"):
            self._tag = tag; self._buf = ""
    def handle_endtag(self, tag):
        if tag == self._tag:
            txt = re.sub(r"\s+"," ", self._buf).strip()
            if txt: self.blocks.append((tag, txt))
            self._tag = None; self._buf = ""
    def handle_data(self, data):
        if self._tag: self._buf += data

US_RE = re.compile(r"US-?\s*(\d+)\s*[·:\-]\s*(.+)", re.I)

def parse_prd(html, cfg):
    p = PRDParser(); p.feed(html)
    blocks = p.blocks
    conv = cfg["prd_field_conventions"]

    stories = []
    cur = None
    for tag, txt in blocks:
        m = US_RE.match(txt) if tag in ("h2","h3") else None
        if m:
            if cur: stories.append(cur)
            summary = m.group(2).strip()
            cur = {"us": f"US-{m.group(1)}", "summary": summary,
                   "desc_lines": [], "subtasks": [],
                   "assignee": None, "points": None}
            # field mềm nhúng trong heading: [assignee: x] [point: N]
            a = re.search(re.escape(conv["assignee_marker"])+r"\s*([^\]]+)\]", txt)
            pt = re.search(re.escape(conv["point_marker"])+r"\s*([\d.]+)\]", txt)
            if a: cur["assignee"] = a.group(1).strip()
            if pt: cur["points"] = float(pt.group(1))
        elif cur is not None:
            if txt.lower().startswith(("edge","ui:","component")): 
                cur["desc_lines"].append(txt)
            elif tag == "li":
                cur["desc_lines"].append("• " + txt)
                # sub-task tường minh: "Sub-task: <tên> - Np"
                sm = re.match(r"sub-?task[:\s]+(.+)", txt, re.I)
                if sm:
                    body = sm.group(1)
                    pm = re.search(r"-\s*(\d+(?:\.\d+)?)\s*p\b", body, re.I)
                    cur["subtasks"].append({
                        "summary": re.sub(r"-\s*\d+(?:\.\d+)?\s*p\b","",body,flags=re.I).strip(" -"),
                        "points": float(pm.group(1)) if pm else None})
            else:
                cur["desc_lines"].append(txt)
    if cur: stories.append(cur)
    return stories

# ---------------- Build Jira payload ----------------
def _clean_desc(desc_lines):
    """Chỉ giữ user story + acceptance criteria. Bỏ dòng Edge/UI/Component metadata."""
    out = []
    for ln in desc_lines:
        low = ln.lower().lstrip("• ").strip()
        if low.startswith(("edge:", "ui:", "component", "edge ")):
            continue
        out.append(ln)
    return out

SPRINT_CODE_RE = re.compile(r"(\d{2}\.\d{2}\.[A-Z])")

def fetch_sprint_id(cfg, sprint_name):
    """Hướng B: tra sprint ID số từ Jira Agile API theo MÃ sprint (vd 26.08.B),
    khớp 'chứa mã' nên bỏ qua tiền tố tên ('PCF-FS Investment ...'). Trả (id, warn)."""
    board_id = cfg.get("sprint_cadence", {}).get("_board_id")
    if not board_id:
        return None, "chưa cấu hình _board_id trong sprint_cadence"
    m = SPRINT_CODE_RE.search(sprint_name or "")
    if not m:
        return None, f"không trích được mã sprint từ '{sprint_name}'"
    code = m.group(1)
    url = f"{JIRA_DOMAIN}/rest/agile/1.0/board/{board_id}/sprint?state=active,future"
    st, data = _req(url)
    if st != 200:
        return None, f"Agile API lỗi {st}"
    matches = [s for s in data.get("values", []) if code in s.get("name", "")]
    if not matches:
        return None, f"không thấy sprint chứa mã '{code}' trên board {board_id}"
    # ưu tiên future (sprint kế tiếp) nếu có nhiều
    matches.sort(key=lambda s: 0 if s.get("state") == "future" else 1)
    return matches[0]["id"], None

def resolve_workstream(cfg, workstream):
    """Từ workstream -> suy (workstream, product_domain, sub_domain). Trả (dict, warn).
    Giống auto-fill trên web: PO chỉ cần chọn workstream."""
    wm = cfg.get("workstream_mapping")
    if not wm:
        # fallback: dùng thẳng defaults nếu chưa có mapping
        d = cfg["defaults"]
        return {"workstream": d.get("workstream"), "product_domain": d.get("product_domain"),
                "sub_domain": d.get("sub_domain")}, None
    ws = (workstream or "").strip().lower()
    for row in wm["rows"]:
        if row["workstream"].lower() == ws:
            return dict(row), None
    valid = ", ".join(r["workstream"] for r in wm["rows"])
    return None, f"workstream '{workstream}' không có trong mapping. Hợp lệ: {valid}"

def resolve_sprint(cfg, today=None):
    """Suy next sprint theo cadence: sprint có start nhỏ nhất trong các sprint
    thoả start >= today - grace_days. Trả (name, None) hoặc (None, cảnh báo)."""
    cad = cfg.get("sprint_cadence")
    if not cad or not cad.get("sprints"):
        return None, "chưa có sprint_cadence trong config"
    today = today or date.today()
    grace = cad.get("_grace_days", 2)
    cutoff = today - timedelta(days=grace)
    cand = [s for s in cad["sprints"]
            if date.fromisoformat(s["start"]) >= cutoff]
    if not cand:
        return None, f"hết cadence (today={today}); cần nạp sprint mới"
    return min(cand, key=lambda s: s["start"])["name"], None

def resolve_reporter(cfg, sub_domain, story_text=""):
    """Suy reporter theo product (sub_domain). FS Hub xét keyword per-story.
    Trả (reporter, warn)."""
    rr = cfg.get("reporter_rules")
    if not rr:
        return cfg["defaults"].get("reporter"), None
    sd = (sub_domain or "").lower()
    text = (story_text or "").lower()
    fh = rr["fs_hub"]
    if any(a in sd for a in fh["_is_fshub_alias"]):
        for rep, kws in fh.items():
            if rep.startswith("_"):
                continue
            if any(k in text for k in kws):
                return rep, None
        w = (f"FS Hub nhưng không rõ fixed-rule/data-model → tạm {fh['_unclear']}, PO check"
             if fh.get("_unclear_warn") else None)
        return fh["_unclear"], w
    for rep, aliases in rr["by_product"].items():
        if rep.startswith("_"):
            continue
        if any(a in sd for a in aliases):
            return rep, None
    return rr["_default_fallback"], f"không match product '{sub_domain}' → fallback"

def build_payload(story, cfg, sprint_id=None):
    d = cfg["defaults"]; fid = cfg["field_ids"]
    dropdowns = set(cfg.get("dropdown_fields", []))
    fields = {
        "project": {"key": d["project_key"]},
        "summary": story["summary"],
        "issuetype": {"name": cfg["issue_types"]["story"]},
        "description": "\n".join(_clean_desc(story["desc_lines"])[:25]),
    }
    if fid.get("story_points") and story["points"] is not None:
        fields[fid["story_points"]] = story["points"]

    # Epic Link: nhận mã epic (PCFFS-xxxx) dạng text
    if fid.get("epic_link") and d.get("epic"):
        fields[fid["epic_link"]] = d["epic"]

    # 3 field dropdown: suy từ workstream (auto-fill product_domain + sub_domain)
    ws_vals, _ = resolve_workstream(cfg, d.get("workstream"))
    if ws_vals:
        for key in ("workstream", "product_domain", "sub_domain"):
            if fid.get(key) and ws_vals.get(key):
                fields[fid[key]] = ({"value": ws_vals[key]} if key in dropdowns else ws_vals[key])

    if story["assignee"]:
        fields["assignee"] = {"name": story["assignee"]}   # DC dùng username

    # Sprint: dùng id đã tra sẵn (1 lần cho cả lô, truyền từ ngoài vào)
    if fid.get("sprint") and sprint_id:
        fields[fid["sprint"]] = sprint_id

    # Reporter suy theo product (sub_domain đã suy từ workstream) + keyword FS Hub per-story
    sub_dom = ws_vals.get("sub_domain") if ws_vals else d.get("sub_domain")
    rep, _ = resolve_reporter(cfg, sub_dom,
                              f"{story.get('summary','')} {' '.join(story.get('desc_lines',[]))}")
    if rep:
        fields["reporter"] = {"name": rep}
    return fields

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prd"); ap.add_argument("--create", action="store_true")
    ap.add_argument("--list-fields", action="store_true")
    ap.add_argument("--inspect", metavar="ISSUE_KEY",
                    help="Đọc 1 ticket thật để lấy field ID + format (vd PCFFS-20144)")
    ap.add_argument("--config", default="jira_config.json")
    ap.add_argument("--insecure", action="store_true",
                    help="Tắt verify SSL (dùng cho Jira nội bộ self-signed cert). "
                         "Chỉ dùng trong mạng công ty/VPN.")
    ap.add_argument("--cacert", metavar="PEM",
                    help="Đường dẫn file CA nội bộ để verify (an toàn hơn --insecure)")
    a = ap.parse_args()

    global SSL_CTX
    if a.cacert:
        SSL_CTX = ssl.create_default_context(cafile=a.cacert)
    elif a.insecure:
        SSL_CTX = ssl._create_unverified_context()
        print("⚠️  SSL verify TẮT (--insecure). Chỉ an toàn với host nội bộ qua mạng công ty.\n")

    if a.list_fields: list_fields(); return
    if a.inspect: inspect(a.inspect); return
    if not a.prd: sys.exit("Cần --prd <file.html>")

    cfg = load_config(a.config)
    html = open(a.prd, encoding="utf-8").read()
    stories = parse_prd(html, cfg)
    if not stories: sys.exit("Không tìm thấy US-xx trong PRD.")

    sprint, warn = resolve_sprint(cfg)
    sp_id, sp_warn = (fetch_sprint_id(cfg, sprint) if sprint and cfg["field_ids"].get("sprint") else (None, None))
    if sprint:
        id_part = f" [id={sp_id}]" if sp_id else (f" [⚠ {sp_warn}]" if sp_warn else " [chưa gán id]")
        sprint_line = f"🗓  Sprint auto-fill: {sprint}{id_part}  (PO kiểm ở đây)"
    else:
        sprint_line = f"⚠  Sprint KHÔNG suy được: {warn}"
    ws_vals, ws_warn = resolve_workstream(cfg, cfg["defaults"].get("workstream"))
    if ws_vals:
        ws_line = (f"🏷  Workstream: {ws_vals['workstream']} → Product Domain: "
                   f"{ws_vals['product_domain']} · Sub Domain: {ws_vals['sub_domain']}")
        sub_dom = ws_vals["sub_domain"]
    else:
        ws_line = f"⚠  Workstream: {ws_warn}"; sub_dom = None
    print(f"\n→ Parse ra {len(stories)} story từ PRD:")
    print(f"   {sprint_line}")
    print(f"   {ws_line}\n")
    for s in stories:
        rep, rwarn = resolve_reporter(cfg, sub_dom,
                                      f"{s.get('summary','')} {' '.join(s.get('desc_lines',[]))}")
        print(f"  {s['us']} · {s['summary']}")
        print(f"       assignee={s['assignee']}  point={s['points']}  "
              f"reporter={rep}  subtasks={len(s['subtasks'])}"
              + (f"\n       ⚠ {rwarn}" if rwarn else ""))
    print("\n" + "="*64)

    if not a.create:
        print("DRY-RUN — payload mẫu cho story đầu:\n")
        print(json.dumps(build_payload(stories[0], cfg, sp_id), ensure_ascii=False, indent=2))
        print("\nThêm --create để tạo thật.")
        return

    if input("Gõ 'yes' để tạo THẬT trên Jira: ").strip().lower() != "yes":
        sys.exit("Huỷ.")
    for s in stories:
        st, data = _req(f"{JIRA_DOMAIN}/rest/api/{JIRA_API}/issue",
                        "POST", {"fields": build_payload(s, cfg, sp_id)})
        if st in (200,201):
            key = data["key"]; print(f"  OK {key}: {s['summary']}")
            for sub in s["subtasks"]:
                sf = {"project":{"key":cfg['defaults']['project_key']},
                      "summary":sub["summary"],
                      "issuetype":{"name":cfg["issue_types"]["subtask"]},
                      "parent":{"key":key}}
                if cfg["field_ids"].get("story_points") and sub["points"]:
                    sf[cfg["field_ids"]["story_points"]] = sub["points"]
                sst, sd = _req(f"{JIRA_DOMAIN}/rest/api/{JIRA_API}/issue","POST",{"fields":sf})
                print(f"      └─ {'OK '+sd['key'] if sst in (200,201) else 'FAIL '+str(sd)}")
        else:
            print(f"  FAIL {s['summary']}: {st} {data}")

if __name__ == "__main__":
    main()
