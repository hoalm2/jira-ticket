---
name: jira-ticket-creator
description: Tạo Jira ticket (User Story + Sub-task) tự động từ PRD cho project PCFFS (Stock/FS Hub, ZaloPay). Dùng skill này BẤT CỨ KHI NÀO PO muốn tạo ticket, đẩy story lên Jira, biến PRD thành ticket, hoặc nhắc tới "tạo ticket từ PRD", "push story lên Jira", "tạo US trên Jira" — kể cả khi không nói chính xác chữ "skill". Skill lo toàn bộ: đọc PRD, điền field từ knowledge có sẵn, dry-run cho PO duyệt, rồi tạo ticket thật qua Jira REST API.
---

# Jira Ticket Creator (PCFFS)

Biến một **source bất kỳ** (PRD, FigJam, Notion, file khai tay…) thành Story +
Sub-task trên Jira DC `jira.zalopay.vn`. Skill KHÔNG bó buộc vào PRD — nó chỉ kiểm
source có cung cấp **đủ schema** không, rồi tự điền các field còn lại từ
`jira_config.json`.

## NGUYÊN TẮC CỐT LÕI: source-agnostic

Skill không quan tâm source là gì. Nó chia field làm 2 nhóm:

- **SOURCE phải cung cấp** (schema đầu vào): `summary`✅, `description`✅, và tuỳ chọn
  `us_id`, `subtasks[]`, `assignee`, `points`.
- **KNOWLEDGE tự fill** (không cần source): project, workstream, product/sub domain,
  epic, reporter, field ID + format dropdown — tất cả từ `jira_config.json`.

Mỗi source cần một parser đổ ra **cùng 1 schema JSON trung gian** (list story). Sau đó
mọi thứ dùng chung. Thêm loại source mới = viết parser mới đổ đúng schema, phần còn lại
tái dùng nguyên.

Style format description (Jira wiki markup, bullet, bold Given/When/Then, heading
*User story*/*Acceptance criteria*) cũng **source-agnostic**: nằm ở
`jira_config.json > description_format`, áp dụng chung cho mọi parser (PRD, FigJam,
source tương lai…), không riêng PRD.

**Luôn in bảng schema cho PO hiểu cái gì họ phải cấp / cái gì máy tự lo:**
```bash
python3 scripts/check_schema.py --show-schema
```

## LUỒNG TỔNG QUÁT

```
SOURCE (PRD / FigJam / bất kỳ)
   → parser tương ứng → schema JSON trung gian (list story)
   → check_schema.py: đủ field bắt buộc chưa? (thiếu → báo PO, dừng)
   → ghép knowledge (jira_config.json): domain, epic, field ID, format
   → DRY-RUN: in bảng ticket, chờ PO gõ 'yes'
   → CREATE: POST Jira, Story rồi Sub-task (parent = story)
   → ghi mapping us→key (cho link-back sau)
```

## BƯỚC 0 — PREFLIGHT CHECK (LÀM ĐẦU TIÊN, MỖI LẦN)

Trước khi làm gì, kiểm tra đủ điều kiện chưa. Chạy check này và báo PO thiếu gì:

```bash
cd <thư mục skill>
echo "== Preflight =="
python3 -c "import sys; print('Python', sys.version.split()[0])"
[ -n "$JIRA_TOKEN" ] && echo "✓ JIRA_TOKEN đã set" || echo "✗ THIẾU JIRA_TOKEN"
[ -n "$JIRA_DOMAIN" ] && echo "✓ JIRA_DOMAIN=$JIRA_DOMAIN" || echo "✗ THIẾU JIRA_DOMAIN"
[ -f jira_config.json ] && echo "✓ có jira_config.json" || echo "✗ THIẾU jira_config.json"
python3 -c "import json;c=json.load(open('jira_config.json'));ids=c['field_ids'];miss=[k for k,v in ids.items() if v is None and not k.startswith('_')];print('✓ field_ids đã điền' if not miss else '⚠ field_ids còn trống: '+','.join(miss))" 2>/dev/null || echo "✗ jira_config.json lỗi/thiếu"
```

**Nếu thiếu, hướng dẫn PO setup theo đúng phần dưới — ĐỪNG chạy tiếp khi chưa đủ.**

### Thiếu JIRA_TOKEN → hướng dẫn:
PAT của Jira (KHÁC PAT Confluence). Tạo tại `jira.zalopay.vn` → avatar →
Profile → Personal Access Tokens → Create. Rồi:
```bash
export JIRA_TOKEN='<PAT Jira>'          # KHÔNG dán token vào chat/commit
export JIRA_DOMAIN='https://jira.zalopay.vn'
```
Lưu ý: env chỉ sống trong terminal đang mở; mở terminal mới phải export lại.

### Thiếu jira_config.json HOẶC field_ids còn trống → sinh/điền config:
Đây là **knowledge nền**, chỉ làm 1 lần/project (hoặc khi Jira đổi field).
Dò field ID thật từ 1 ticket mẫu bất kỳ của project:
```bash
python3 scripts/prd_to_jira.py --inspect <TICKET-MẪU> --insecure
```
Lệnh in ra customfield ID + format (dropdown {value} / epic link text key…).
Copy các ID (Story Points, Workstream, Product Domain, Sub Domain, Epic Link) vào
`jira_config.json > field_ids`. Xem giá trị mặc định (reporter, epic, domain) trong
`jira_config.json > defaults` và chỉnh cho đúng PRD hiện tại.

### Lỗi SSL (self-signed certificate) → thêm cờ:
Jira nội bộ dùng cert tự ký. Thêm `--insecure` vào mọi lệnh (chạy trong mạng
công ty/VPN là an toàn). Sạch hơn: xin CA nội bộ từ IT rồi dùng `--cacert <file.pem>`.

## BƯỚC 1 — CONFIRM EPIC (BẮT BUỘC, trước khi dựng khung ticket)

Epic **đổi hằng sprint** → KHÔNG dùng epic hardcode trong config. Luôn confirm với PO:

1. Hỏi PO story này thuộc epic nào (tên hoặc key).
2. Tra trong danh sách 192 epic:
```bash
python3 scripts/epic_check.py --find "<tên PO nêu>"    # hoặc --key PCFFS-xxxx
```
   - Khớp chính xác → dùng key đó, điền vào `jira_config.json > defaults > epic`.
   - Khớp gần đúng → đưa danh sách gợi ý cho PO chọn.
   - Không thấy → có thể epic MỚI, sang (3).
3. Nếu PO muốn tạo epic mới → **scan trùng trước khi tạo**:
```bash
python3 scripts/epic_check.py --new "<tên epic mới PO đề xuất>"
```
   - Có ứng viên trùng → **báo PO**, để PO quyết: dùng lại epic cũ hay vẫn tạo mới.
   - Không trùng → PO xác nhận tên cuối, rồi mới tạo epic (thao tác tạo epic tách riêng).

**Không tự chọn epic thay PO. Không bỏ qua bước scan trùng khi tạo epic mới.**
`epics.json` cập nhật định kỳ (epic mới sinh mỗi sprint) — xem `_updated` trong file.

## BƯỚC 2 — NHẬN SOURCE & KIỂM SCHEMA

PO cung cấp source theo bất kỳ cách nào:
- **Upload file** (PRD `.html`/`.md`, export FigJam, JSON khai tay…).
- **Link** (Confluence PRD, FigJam board…) → dùng parser/fetch tương ứng.

**Đầu tiên, in bảng schema cho PO** để họ biết source cần đắp gì:
```bash
python3 scripts/check_schema.py --show-schema
```

Chọn/chạy parser hợp với source để ra **schema JSON trung gian** (list story, đúng
các field ở bảng trên). Hiện có:
- PRD → dùng `prd_to_jira.py` (parse sẵn, xuất story theo schema).
- FigJam / source khác → parser riêng (roadmap; đổ ra cùng schema).

**Rồi kiểm schema — cửa chặn bắt buộc:**
```bash
python3 scripts/check_schema.py <stories.json>
```
- Đủ field bắt buộc → sang Bước 3 (dry-run).
- Thiếu (vd story nào đó không có `description`) → **báo PO đúng story + field thiếu,
  DỪNG lại.** Không tự bịa nội dung cho đủ.

Convention khi source là PRD: mỗi US là heading `US-xx · <summary>` + Acceptance
criteria; sub-task tường minh `Sub-task: <tên> - Np`; field mềm `[assignee: x] [point: N]`.

**Convention format description (Jira wiki markup, áp dụng chung mọi source, không
riêng PRD):**
- Description tách 2 khối rõ ràng: `*User story*` (đoạn tường thuật) rồi
  `*Acceptance criteria*` (list). Bold + heading dùng cú pháp Jira wiki markup thật
  (`*text*`), KHÔNG phải markdown (`**text**`).
- List dùng bullet `* ` (Jira wiki list thật), không dùng ký tự `•`.
- Given/When/Then/And được tự động bold + tự chèn dấu chấm giữa các vế nếu PRD viết
  liền 1 câu không tách câu.
- AC theo từng use case (PRD nhiều case như FD) giữ **cấu trúc phân cấp**: dòng
  sub-heading dạng "1. Tên case" in bold đứng riêng, các Given/When/Then thuộc case đó
  lùi cấp (`** `) bên dưới — không bị làm phẳng thành 1 list.
- Toàn bộ style này (bullet, từ khoá bold, regex nhận heading case, tên 2 heading) là
  **knowledge config-driven** trong `jira_config.json > description_format` — sửa ở đó
  khi cần đổi style, KHÔNG sửa code trong `prd_to_jira.py`.

## BƯỚC 3 — DRY-RUN (BẮT BUỘC, trước mọi lần tạo)

```bash
python3 scripts/prd_to_jira.py --prd <đường-dẫn-PRD> --insecure
```
In ra: số story parse được + payload mẫu. **Đưa bảng này cho PO xem và xác nhận.**
Kiểm cùng PO: summary đúng chưa, description sạch chưa, epic/domain đúng chưa,
assignee/point có chưa (nếu PRD đã bổ sung).

## BƯỚC 4 — TẠO THẬT

Chỉ chạy sau khi PO duyệt dry-run:
```bash
python3 scripts/prd_to_jira.py --prd <đường-dẫn-PRD> --create --insecure
```
Script sẽ hỏi gõ `yes` lần nữa. Sau khi tạo:
- In `OK PCFFS-xxxxx` cho mỗi story/sub-task.
- **Bảo PO mở 1 ticket trên Jira soát 4 thứ:** description, 3 dropdown
  (Workstream/Product Domain/Sub Domain), epic link, sub-task có nằm dưới story cha.

## RULE HÀNH VI (quan trọng)

- **Không bao giờ dán/log PAT ra chat.** Chỉ đọc từ env `JIRA_TOKEN`.
- **Mặc định dry-run.** Không bao giờ tự chạy `--create` khi PO chưa duyệt bản preview.
- **Field chưa biết thì để trống, KHÔNG đoán.** `field_ids` null → bỏ field đó, đừng
  gửi bừa (dropdown sai giá trị sẽ bị Jira reject cả ticket).
- **Description chỉ chứa user story + acceptance criteria.** Bỏ metadata thừa
  (dòng `[US-xx]`, `Edge:`, `UI:`, `Sprint/Epic`) — epic/sprint đã có field riêng.
  Và trình bày theo Jira wiki markup ở trên (`*User story*` / `*Acceptance
  criteria*`, bullet `* `, bold Given/When/Then/And) — không phải text thô.
- **Workstream → tự suy Product Domain + Sub Domain** (như auto-fill web). PO chỉ cần
  cho biết 1 workstream; 2 field kia suy từ `jira_config.json > workstream_mapping`. Cả 3
  là dropdown, gửi `{value:...}`. Workstream lạ (không trong mapping) → cảnh báo + liệt kê
  hợp lệ. Sub Domain suy được cũng là input cho rule reporter.
- **Epic KHÔNG hardcode — luôn confirm PO trước (Bước 1).** Epic đổi hằng sprint. Dùng
  `epic_check.py` tìm khớp; nếu PO tạo epic mới, BẮT BUỘC scan trùng (`--new`) và để PO
  quyết. Không tự chọn epic thay PO.
- **Sprint tự suy từ cadence + gán id thật (hướng B), KHÔNG hỏi PO.** Rule chọn sprint:
  start_date nhỏ nhất trong các sprint thoả `start_date ≥ hôm nay − 2 ngày`. Rồi tra
  **sprint id số** qua Agile API (`board/<_board_id>/sprint`), khớp theo mã `26.xx.X` nên
  bỏ qua tiền tố tên ("PCF-FS Investment ..."). Field sprint (greenhopper) nhận id số, không
  nhận tên. Nếu sprint chưa tồn tại trên Jira (tương lai xa) → cảnh báo, không gán. Dry-run
  hiện cả tên + id để PO kiểm.
- **Reporter tự suy theo product, KHÔNG hardcode.** Map trong `jira_config.json >
  reporter_rules`: Stock/FC/Crypto→hoalm2, MMF→thitb, Insurance/FD→trangdhq. Riêng
  **FS Hub xét keyword per-story**: "fixed rule"/"portfolio"/"asset detail"→hoalm2,
  "data model"→thitb, không rõ→hoalm2 + cảnh báo PO check. Product lấy từ `sub_domain`.
- **Idempotent:** nếu chạy lại, story đã có key trong mapping thì skip, không tạo trùng.
- **Lỗi từng ticket độc lập:** 1 cái fail không chặn cả lô; log rõ cái nào fail vì sao.
- Nếu `--create` báo `customfield_xxxxx is required` → project bắt buộc field ẩn
  (vd Priority, ZLP Environment). Thêm field đó vào `defaults` + `field_ids` rồi chạy lại.

## CẤU TRÚC SKILL

```
jira-ticket-creator/
├── SKILL.md                  ← file này: luồng + preflight + rule hành vi
├── jira_config.json          ← knowledge PO maintain (defaults + field_ids + dropdown + rules)
├── epics.json                ← danh sách epic (đổi hằng sprint; cập nhật định kỳ)
└── scripts/
    ├── check_schema.py       ← cửa kiểm source-agnostic: in schema + validate
    ├── epic_check.py         ← confirm epic: tìm khớp + scan trùng khi tạo epic mới
    └── prd_to_jira.py        ← engine: inspect / dry-run / create (+ parser PRD)
```

Chi tiết từng file:

- **`SKILL.md`** — luồng chạy, preflight check, rule hành vi. Đọc đầu tiên.
- **`jira_config.json`** — **knowledge PO maintain**: `defaults` (reporter, epic, domain,
  sprint), `field_ids` (map customfield), `dropdown_fields`. Cập nhật ở đây khi đổi
  epic/sprint/PRD — **KHÔNG nạp knowledge qua chat** (chat mất khi đổi session).
- **`scripts/check_schema.py`** — cửa kiểm **source-agnostic**. `--show-schema` in bảng
  2 nhóm field cho PO; truyền file JSON để kiểm đủ field bắt buộc chưa. Chạy trước khi tạo.
- **`epics.json`** — danh sách 192 epic (key + label + summary). **Đổi hằng sprint** →
  cập nhật định kỳ. `epic_check.py` đọc file này để confirm/scan trùng.
- **`scripts/epic_check.py`** — `--find` tìm epic PO nêu, `--new` scan trùng cho epic mới,
  `--key` tra theo key. Dùng ở Bước 1 (confirm epic).
- **`scripts/prd_to_jira.py`** — engine. Gồm: `--inspect` (dò field ID từ ticket mẫu),
  `--prd` dry-run, `--create`. Có sẵn parser PRD. Không sửa khi dùng thường.

## ROADMAP (chưa có — thêm dần vào scripts/ khi PO chuẩn bị xong)

Mỗi lần thêm, cập nhật lại phần CẤU TRÚC ở trên:
- `scripts/parsers/figjam_parser.py` — parser FigJam, đổ ra cùng schema trung gian.
- Script fetch PRD từ link Confluence (`GET /rest/api/content/{id}?expand=body.storage`).
- Validate mở rộng trong `check_schema.py`: assignee hợp lệ, dropdown value hợp lệ.
- Sprint cadence trong `jira_config.json` → tự suy next sprint.
- `scripts/link_prd.py` — link-back ticket ↔ Confluence PRD (bảng tổng hợp theo US).
