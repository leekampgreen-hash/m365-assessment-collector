# Collector Standardization Backlog & Roadmap

Dokumen ini melacak rencana standardisasi penamaan, registrasi, dan pemanggilan seluruh collector di M365 Assessment Collector.

---

## Ringkasan Inisiatif

Saat ini terdapat lebih dari 40 collector dan endpoint audit yang terbagi ke dalam format berbeda-beda (`G01-xxx`, `USAGE-xxx`, `TM-001`, `DEF-P0x`, `DLP-P0x`, `OD-AUDIT`, `SP-A01`, serta script modul snake_case).
Inisiatif ini menstandarkan seluruh penamaan collector, cara pemanggilan (CLI/Scheduler), registrasi inventaris, hingga pelaporan status checkpoint.

---

## Tahapan Pekerjaan

### [x] Tahap 1: Perbaikan Bug Naming di Scheduler (Prioritas Cepat)
- **Status:** COMPLETED
- **Tujuan:** Menghilangkan kegagalan eksekusi job background akibat ketidakcocokan flag CLI antara `scheduler.py` dan `run_collector.py`.
- **Rincian Perbaikan:**
  1. Perbaiki `special_flags` di `collectors/scheduler.py`:
     - Ganti `"--defender-summary"` menjadi `"--defender-devices"`.
       *(Sebelumnya gagal dengan exit code 2: `unrecognized arguments: --defender-summary`)*.
     - Ganti `"--entra-stale"` menjadi `"--entra-stale-devices"` secara eksplisit.
     - Tambahkan mapping untuk `intune_compliance_policies` (`--intune-compliance-policies`), `intune_mobile_apps` (`--intune-mobile-apps`), dan `onedrive_audit` (`--onedrive-audit`).
  2. Tambahkan alias backward-compatibility di `collectors/run_collector.py`:
     - `--defender-summary` sebagai alias ke `--defender-devices`.
     - `--entra-stale` sebagai alias ke `--entra-stale-devices`.
- **Verifikasi:**
  - Dry-run sukses untuk `--defender-devices`, `--defender-summary`, `--entra-stale-devices`, `--entra-stale`.
  - Service scheduler dapat menjalankan job tanpa error argument argparse.

---

### [x] Tahap 2: Daftarkan Semua Specialized Collectors ke `config/api_inventory.json`
- **Status:** COMPLETED
- **Tujuan:** Menjadikan `config/api_inventory.json` sebagai **Single Source of Truth (SSOT)** untuk semua collector (menghilangkan hardcoded collector di berbagai file).
- **Rincian Pekerjaan & Implementasi:**
  1. Mendaftarkan 12 specialized collectors ke `config/api_inventory.json`:
     - `OD-AUDIT` (`onedrive_audit`) -> OneDrive High-Value Audit
     - `SP-A01` (`sharepoint_audit`) -> SharePoint High-Value Audit
     - `SP-SITES` (`sharepoint_sites`) -> SharePoint Site Inventory
     - `INTUNE-001` (`intune_compliance`) -> Intune Device Compliance
     - `INTUNE-002` (`intune_enrollment`) -> Intune Device Enrollment
     - `INTUNE-003` (`intune_compliance_policies`) -> Intune Compliance Policies
     - `INTUNE-004` (`intune_mobile_apps`) -> Intune Mobile Apps
     - `ENTRA-GUESTS` (`entra_guests`) -> Entra Guest User Inventory
     - `ENTRA-AUTH` (`entra_auth_methods`) -> Entra Authentication Methods
     - `ENTRA-STALE` (`entra_stale_devices`) -> Entra Stale Device Inventory
     - `ENTRA-PIM` (`entra_pim`) -> Entra PIM Assignments
     - `DEF-DEV` (`defender_devices`) -> Defender Device Threats
  2. Menambahkan metadata schema terstandar: `collector_type`, `module`, `function`, `cli_flag`, `table`, `permission`, dan `documented_permissions`.
  3. Menambahkan `SPECIALIZED_ENDPOINT_MAP` di `collectors/run_collector.py` sehingga pemanggilan via `--endpoint <ID>` (misal `--endpoint ENTRA-GUESTS` atau `--endpoint INTUNE-001`) dapat langsung mendispatch ke modul fungsi collector yang sesuai.
  4. Menambahkan proteksi deduplikasi di `api/admin.py` pada loop status collector agar tampilan di Admin Dashboard UI tidak menduplikasi baris collector.
- **Verifikasi:**
  - `load_inventory("config/api_inventory.json")` berhasil memuat 45 specs valid.
  - Dry-run untuk `--endpoint ENTRA-GUESTS`, `--endpoint INTUNE-001`, `--endpoint DEF-DEV`, `--endpoint OD-AUDIT`, `--endpoint G01-001`, dan `--all` PASS (exit code 0).
  - Evaluasi endpoint `/api/admin/collector/status` menghasilkan 45 entri unik tanpa duplikasi.

---

### [x] Tahap 3: Implementasikan Unified Runner, Mapping Standar Baru & Sinkronisasi DB Checkpoint
- **Status:** COMPLETED
- **Tujuan:** Menyediakan satu pintu pemanggilan CLI (`--collector <ID_OR_NAME>`), pemetaan alias standar baru, dan pembersihan duplikasi checkpoint di database.
- **Rincian Pekerjaan yang Diselesaikan:**
  1. **Unified CLI Runner (`--collector <ID_OR_NAME>`):**
     - Ditambahkan flag `--collector` di `collectors/run_collector.py`.
     - Fungsi `_resolve_collector` secara cerdas dan fleksibel memetakan nama apa pun:
       - Shortcut slug: `users`, `groups`, `organization`, `directory_roles`, `mfa_registration`, `sp_settings`, dll.
       - Specialized slug: `entra_guests`, `intune_compliance`, `defender_devices`, `onedrive_audit`, `sharepoint_audit`, dll.
       - Standard code / endpoint ID: `G01-001`, `OD-AUDIT`, `INTUNE-001`, `ENTRA-GUESTS`, `DEF-DEV`, `USAGE-001`, dll.
       - Batch2 source: `DEF-P02`, `DEF-P03`, `DLP-P01`, `DLP-P02`, `defender_alerts`, `dlp_alerts`, dll.
       - Security rules: `SEC-E01`, `M365-ENTRA-CA-ENFORCEMENT-001`, dll.
     - Dukungan dry-run aman untuk semua variasi pemanggilan (`--collector <NAME> --dry-run`).
  2. **Sinkronisasi Checkpoint Database (`control.collector_checkpoint`):**
     - Dilakukan sinkronisasi timestamp dua arah antara entri lama (`onedrive_audit`, `sharepoint_audit`) dan entri standar (`OD-AUDIT`, `SP-A01`) di PostgreSQL container.
  3. **Refaktor Admin API (`/api/admin/collector/status`):**
     - Menghapus array hardcoded `special_collectors` di `api/admin.py`.
     - Menggunakan `config/api_inventory.json` sebagai Single Source of Truth (SSOT).
     - Menambahkan mekanisme dual-lookup (mencocokkan `ep["id"]` maupun `ep["key"]` ke tabel checkpoint/runs) dengan pemilihan checkpoint teranyar, serta menyertakan field `slug`.
     - Container `graph-agent-operations-api-dev` direstart dan diverifikasi live: mengembalikan 45 baris collector lengkap, tanpa duplikasi (`Has duplicates: False`).
- **Verifikasi:**
  - CLI dry-run multi-variasi (slug, ID standar, specialized, batch2, security-rule, unknown identifier) PASS sesuai spesifikasi.
  - Seluruh unit & integration test suite (`test_auth_runtime_cli.py`, `test_discovery_agent.py`, `test_g09_r2_normalization_handoff.py` - total 153 tests) PASS 100%.
  - API endpoint `/api/admin/collector/status` live mengembalikan tepat 45 baris tanpa duplikasi dengan status dan timestamp GMT+7 sinkron.

---

### [x] Tahap 4: UI Monitoring Enhancement, Scheduler Modernization & Reference Catalog
- **Status:** COMPLETED
- **Tujuan:** Menyempurnakan antarmuka operasional (UI Admin), memodernisasi eksekusi scheduler otomatis dengan unified runner, dan menyusun kamus referensi resmi.
- **Rincian Pekerjaan yang Diselesaikan:**
  1. **Penyempurnaan UI Admin Dashboard (`operations-ui/public/admin.html`):**
     - Ditambahkan **Search Bar** instan untuk memfilter kolektor berdasarkan ID, slug, atau nama.
     - Ditambahkan **Dropdown Filter Workload** (Semua, Entra ID, Intune, Defender, Purview, SharePoint, OneDrive, Usage Reports).
     - Ditambahkan tombol aksi **Copy CLI Command** (menyalin perintah `python -m collectors.run_collector --collector <ID>` ke clipboard).
     - Ditambahkan tombol **Refresh** untuk pembaruan status data langsung.
  2. **Modernisasi Scheduler (`collectors/scheduler.py`):**
     - Menyederhanakan method dispatch scheduler sehingga memanggil runner terpadu `["--collector", <NAME>]` untuk seluruh endpoint, specialized collectors, security rules, dan batch-2 security sources.
     - Container scheduler `graph-agent-scheduler-dev` direstart dan diverifikasi live: seluruh 20+ job berjalan sesuai jadwal tanpa exception.
  3. **Dokumentasi Kamus Referensi Kolektor (`docs/COLLECTORS_REFERENCE.md`):**
     - Disusun katalog referensi komprehensif berisi tabel lengkap 45 kolektor data (ID standar, alias/slug, izin Graph, tabel target PostgreSQL, dan frekuensi jadwal cron).
- **Verifikasi:**
  - Fungsionalitas UI live di port 18080 terverifikasi menyajikan elemen pencarian, filter workload, dan tombol copy CLI.
  - Scheduler container berjalan aktif dan terjadwal normal.
  - Seluruh 153 skenario unit test PASS 100%.

---

### [x] Tahap 5: Advanced Operational Capabilities (On-Demand Execution, Metric Cards & Inspector Modal)
- **Status:** COMPLETED
- **Tujuan:** Menyediakan kapabilitas operasional tingkat lanjut melalui UI Admin dan API: eksekusi kolektor on-demand (Run Now), 4 kartu metrik agregasi kesehatan, serta modal inspektur spesifikasi teknis lengkap.
- **Rincian Pekerjaan yang Diselesaikan:**
  1. **Backend API Trigger Endpoint (`api/admin.py`):**
     - Diimplementasikan endpoint `POST /api/admin/collector/trigger` dengan autentikasi `SUPER_ADMIN`.
     - Endpoint menerima parameter `{ "collector_id": "<ID_OR_NAME>", "dry_run": false }` dan menjalankan Unified Runner `python3 -m collectors.run_collector --collector <ID>` dengan safety timeout 60 detik.
     - Diperkaya endpoint `GET /api/admin/collector/status` dengan metadata teknis tambahan per entri: `permission`, `table`, dan `endpoint_route`.
  2. **Kartu Metrik Agregasi Operasional (`operations-ui/public/admin.html`):**
     - Ditambahkan 4 Summary Cards di bagian atas tabel Collector Checkpoints:
       - **Total Registered:** 45 kolektor data aktif.
       - **Healthy (<24h):** Jumlah kolektor dengan checkpoint mutakhir dalam kurun waktu 24 jam terakhir.
       - **Stale (>24h):** Jumlah kolektor dengan checkpoint lebih dari 24 jam.
       - **Pending / Inactive:** Jumlah kolektor yang belum memiliki rekaman checkpoint.
  3. **Aksi Tombol "Run Now" & Indikator Loading:**
     - Ditambahkan tombol aksi **Run** di setiap baris tabel serta tombol **Run Collector Now** di dalam modal inspeksi.
     - Dilengkapi status loading spinner (`ti-loader ti-spin`) saat eksekusi berjalan dan auto-refresh tabel + notifikasi toast setelah selesai.
  4. **Collector Inspector Modal Dialog:**
     - Ditambahkan tombol aksi **Inspect** di setiap baris tabel kolektor.
     - Modal interaktif menampilkan detail lengkap:
       - Standard Collector ID & Slug/Key
       - Workload Domain (Entra, Intune, Defender, Purview, dll.)
       - Required Microsoft Graph API Permission
       - Waktu Checkpoint Terakhir (GMT+7) dan Badge Status Kesehatan (Healthy / Stale / Pending)
       - Perintah CLI Unified Runner dengan tombol Quick Copy
  5. **Live Verification & Testing:**
     - Endpoint `POST /api/admin/collector/trigger` terverifikasi sukses menjalankan kolektor via proxy Nginx port 18080.
     - Seluruh 153 unit test PASS tanpa regresi.
