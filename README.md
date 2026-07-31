# Jira Ticket Creator — Skill cho PO (PCFFS)

Skill giúp PO tạo Jira Story + Sub-task tự động từ PRD (hoặc source khác), tự điền
epic/sprint/reporter/workstream theo knowledge có sẵn, có bước duyệt trước khi ghi Jira.

> **Đọc file này từ đầu đến cuối trước khi dùng.** Làm đúng 3 phần: CÀI → SETUP → DÙNG.

---

## PHẦN 1 — CÀI (đưa skill vào thư mục Claude skills)

Skill phải nằm ở `~/.claude/skills/jira-ticket-creator/` thì Claude Code mới nhận.
Claude Code CHỈ quét thư mục này — **không** quét Downloads hay chỗ khác. Chọn 1 cách:

### Cách A — Clone git (khuyên dùng: `git pull` cập nhật được về sau)
```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
git clone <URL_REPO_NÀY> jira-ticket-creator
chmod +x ~/.claude/skills/jira-ticket-creator/scripts/*.py
```

### Cách B — Tải file zip (nếu chưa dùng git)
Tải `jira-ticket-creator.zip` về máy (thường vào `~/Downloads`). File tải về nằm ở
Downloads là **SAI chỗ** — phải chuyển sang skills folder:
```bash
mkdir -p ~/.claude/skills
# nếu là file .zip:
unzip ~/Downloads/jira-ticket-creator.zip -d ~/.claude/skills/
# HOẶC nếu đã giải nén sẵn thành thư mục trong Downloads, chỉ cần chuyển:
mv ~/Downloads/jira-ticket-creator ~/.claude/skills/

chmod +x ~/.claude/skills/jira-ticket-creator/scripts/*.py
```

### KIỂM TRA đúng chỗ (bước này QUAN TRỌNG — hay sai nhất)
```bash
ls ~/.claude/skills/jira-ticket-creator/SKILL.md
```
- In ra đường dẫn → ĐÚNG chỗ, sang Phần 2.
- Báo `No such file` → sai chỗ. Chạy `find ~/.claude/skills -name SKILL.md` xem nó nằm đâu.

⚠️ **Lỗi hay gặp: lồng 2 lần thư mục.** Nếu thành
`~/.claude/skills/jira-ticket-creator/jira-ticket-creator/SKILL.md` (lặp tên 2 lần) thì
Claude Code KHÔNG nhận. Sửa:
```bash
mv ~/.claude/skills/jira-ticket-creator/jira-ticket-creator/* ~/.claude/skills/jira-ticket-creator/
```

### Xác nhận Claude nhận skill
Mở **session Claude Code mới**, gõ `/skills`. Thấy `jira-ticket-creator` là OK.
Không thấy → kiểm lại `SKILL.md` đúng độ sâu như trên, rồi restart Claude Code.

> **Cá nhân vs team:** đặt ở `~/.claude/skills/` = dùng cho MỌI project của riêng bạn
> (khuyên dùng). Nếu muốn skill đi theo 1 repo team cụ thể, đặt ở `.claude/skills/` (không
> có `~`) bên trong repo đó và commit — cả team clone repo là có skill.

---

## PHẦN 2 — SETUP (làm 1 lần, mỗi PO tự làm trên máy mình)

Skill cần token Jira của **riêng bạn** + Python. Không có sẵn trong repo (token là bí mật).

### 2.1 Tạo PAT Jira (KHÁC PAT Confluence)
Vào `https://jira.zalopay.vn` → avatar góc phải → **Profile** → **Personal Access Tokens**
→ **Create token** → đặt tên (vd `claude-ticket`) → **copy** (chỉ hiện 1 lần).

> ⚠️ KHÔNG dán token vào chat, không commit vào git, không chụp màn hình có token.

### 2.2 Cắm token + domain vào biến môi trường
Trong terminal (mỗi lần mở terminal mới phải chạy lại — xem mẹo bên dưới):
```bash
export JIRA_TOKEN='<PAT Jira của bạn>'
export JIRA_DOMAIN='https://jira.zalopay.vn'
```

**Mẹo khỏi phải export mỗi lần:** thêm 2 dòng trên vào cuối file `~/.zshrc` (macOS) hoặc
`~/.bashrc` (Linux), rồi `source ~/.zshrc`. Token nằm trong file cá nhân trên máy bạn,
KHÔNG trong repo.

### 2.3 Kiểm tra đã đủ điều kiện chưa (preflight)
```bash
cd ~/.claude/skills/jira-ticket-creator
python3 -c "import sys;print('Python',sys.version.split()[0])"
[ -n "$JIRA_TOKEN" ] && echo "✓ JIRA_TOKEN ok" || echo "✗ thiếu JIRA_TOKEN"
```
Hoặc để Claude tự chạy preflight khi bạn gọi skill — nó sẽ báo thiếu gì và hướng dẫn.

### 2.4 (Lần đầu / khi Jira đổi field) — kiểm field ID
Field ID của project đã điền sẵn trong `jira_config.json`. Nếu Jira đổi cấu hình field,
dò lại từ 1 ticket mẫu:
```bash
python3 scripts/prd_to_jira.py --inspect PCFFS-20144 --insecure
```

---

## PHẦN 3 — DÙNG (mỗi lần tạo ticket)

Cách đơn giản nhất: mở Claude Code trong thư mục làm việc, nói tự nhiên, ví dụ:
> "Tạo Jira ticket từ PRD này" (kèm file PRD hoặc link)

Claude sẽ tự chạy skill theo luồng: preflight → confirm epic → kiểm schema → **dry-run
cho bạn duyệt** → tạo thật. Bạn chỉ cần cung cấp:
- **Source**: 1 PRD (file `.html`/`.md`) hoặc link.
- **Epic**: tên epic (Claude sẽ confirm/scan trùng).
- **Workstream**: vd "Stock Trading" (product domain + sub domain tự suy).

Sprint, reporter, domain, format field → skill tự điền. Bạn **duyệt ở bước dry-run** rồi
gõ `yes` để tạo thật.

### Chạy tay (nếu muốn)
```bash
cd ~/.claude/skills/jira-ticket-creator
# xem trước, không ghi Jira:
python3 scripts/prd_to_jira.py --prd <file PRD> --insecure
# tạo thật (hỏi 'yes'):
python3 scripts/prd_to_jira.py --prd <file PRD> --create --insecure
```

Sau khi tạo, **mở 1 ticket trên Jira soát**: description, workstream/domain, epic link,
sub-task nằm dưới story cha.

---

## CẬP NHẬT SKILL (khi có bản mới)

Knowledge (epic, cadence) đổi theo sprint. Lấy bản mới nhất:
```bash
cd ~/.claude/skills/jira-ticket-creator
git pull
```
Không cần cài lại. `git pull` là có epic/cadence/rule mới nhất.

---

## LỖI THƯỜNG GẶP

| Lỗi | Nguyên nhân | Xử lý |
|-----|-------------|-------|
| Skill không hiện trong `/skills` | Đặt sai chỗ / lồng sâu | SKILL.md phải ở `~/.claude/skills/jira-ticket-creator/` |
| `THIẾU JIRA_TOKEN` | Chưa export | Làm lại 2.2; terminal mới phải export lại |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Jira nội bộ self-signed | Thêm `--insecure`, hoặc `--cacert <CA nội bộ>` |
| `401` | PAT sai/hết hạn | Tạo PAT mới (2.1) |
| `403` | Thiếu quyền tạo issue | Xin quyền tạo ticket trong PCFFS |
| `--insecure unrecognized` | Bản cũ | `git pull` lấy bản mới |

Chi tiết luồng + rule: xem `SKILL.md`. Chi tiết setup nâng cao: xem `docs/SETUP.md`.
