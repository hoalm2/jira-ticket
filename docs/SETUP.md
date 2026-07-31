# Setup nâng cao & giải thích knowledge

## Phân biệt config: phần CHUNG (cả team) vs phần THEO PRD (mỗi lần đổi)

`jira_config.json` gồm 2 loại nội dung:

### Phần CHUNG — cả team dùng chung, ít đổi, cập nhật qua git pull
- `field_ids` — customfield ID của project (đổi khi Jira admin đổi cấu hình)
- `sprint_cadence` — lịch sprint (nạp mỗi năm)
- `reporter_rules` — map product → reporter
- `workstream_mapping` — workstream → product/sub domain
- `issue_types`, `dropdown_fields`

→ Khi mấy cái này đổi: 1 người sửa, commit, cả team `git pull`. KHÔNG ai sửa tay lẻ.

### Phần THEO PRD — đổi mỗi lần tạo ticket
- `defaults.epic` — epic của PRD hiện tại (Claude confirm ở Bước 1)
- `defaults.workstream` — workstream của PRD hiện tại

→ Hai cái này Claude sẽ hỏi/confirm khi chạy. Không cần commit thay đổi tạm thời của
chúng lên git (tránh xung đột giữa các PO). Nếu lỡ sửa, `git checkout jira_config.json`
để về bản chung.

## Token: vì sao không nằm trong repo

PAT là bí mật cá nhân, đọc từ env `JIRA_TOKEN`. `.gitignore` đã chặn mọi file token.
Mỗi PO tạo PAT riêng — ticket tạo ra mang danh người chạy, không phải người viết skill.

## Cập nhật epics.json từ Jira (thủ công hiện tại)

`epics.json` đổi hằng sprint. Hiện cập nhật tay: xuất list epic từ Jira → thay file →
commit → team pull. (Roadmap: script tự pull epic mới qua JQL `issuetype = Epic`.)

## SSL self-signed

Jira nội bộ dùng cert tự ký → thêm `--insecure` vào lệnh. Sạch hơn: xin root CA nội bộ
từ IT, lưu ra file `.pem`, dùng `--cacert /path/ca.pem` (verify đầy đủ, không tắt).

## Chạy trong mạng công ty / VPN

`jira.zalopay.vn` chỉ truy cập được trong mạng công ty hoặc qua VPN. Ngoài mạng đó,
mọi lệnh gọi Jira sẽ timeout.
