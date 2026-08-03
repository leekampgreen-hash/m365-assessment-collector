# Microsoft Graph API Testing Framework

Tool sederhana untuk menguji berbagai endpoint Microsoft Graph API menggunakan application credentials. Endpoint GET dapat dipanggil melalui satu command tanpa mengubah source code untuk setiap pengujian.

## Requirements

- Docker dan Docker Compose
- Microsoft Entra ID app registration dengan client credentials flow
- Microsoft Graph application permissions yang sesuai untuk endpoint yang diuji
- Admin consent untuk permissions tersebut

## Environment variables

Buat file `.env` di root project berdasarkan `.env.example`:

```env
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
OUTPUT_DIR=/output
```

`TENANT_ID`, `CLIENT_ID`, dan `CLIENT_SECRET` digunakan untuk memperoleh access token Microsoft Graph. `OUTPUT_DIR` bersifat opsional dan default-nya adalah `/output` di dalam container.

## Docker build

Build image:

```bash
docker compose build
```

Semua contoh command berikut dapat dijalankan melalui service `graph`:

```bash
docker compose run --rm graph python main.py <endpoint>
```

Seluruh command dalam dokumentasi ini telah divalidasi menggunakan Ubuntu Docker runtime.

## Authentication test

Uji apakah client credentials dapat memperoleh token:

```bash
docker compose run --rm graph python auth.py
```

Output yang berhasil:

```text
Authentication Success
```

## Testing endpoints

### Users

```bash
docker compose run --rm graph python main.py users
```

### Groups

```bash
docker compose run --rm graph python main.py groups
```

Gunakan format yang sama untuk endpoint Microsoft Graph lainnya, misalnya:

```bash
docker compose run --rm graph python main.py users/{user-id}/memberOf
```

### Query parameters

Pilih field tertentu dengan `--select`:

```bash
docker compose run --rm graph python main.py users --select id,displayName,userPrincipalName
```

Gunakan filter OData dengan `--filter`:

```bash
docker compose run --rm graph python main.py users --filter "accountEnabled eq true"
```

Batasi jumlah item per halaman dengan `--top`:

```bash
docker compose run --rm graph python main.py groups --top 10
```

Parameter Graph lain dapat ditambahkan berulang kali menggunakan `--param`:

```bash
docker compose run --rm graph python main.py users --param consistencyLevel=eventual
```

## Pagination

Pagination aktif secara default. Jika Microsoft Graph mengembalikan `@odata.nextLink`, tool akan mengambil seluruh halaman dan menggabungkan item ke dalam satu `value` array. Metadata `_pages` menunjukkan jumlah halaman yang diambil.

Untuk hanya mengambil halaman pertama:

```bash
docker compose run --rm graph python main.py users --no-paginate
```

## Output

Output default disimpan sebagai JSON di `/output`. Karena folder `/output` di-container di-mount ke folder `output` di host, hasil tersedia di `output/` project.

Contoh output JSON eksplisit:

```bash
docker compose run --rm graph python main.py users --output /output/users.json
```

Simpan hasil sebagai CSV:

```bash
docker compose run --rm graph python main.py groups --format csv --output /output/groups.csv
```

Jika `--output` tidak diberikan, nama file dibuat dari endpoint, misalnya `users.json` atau `groups.csv`.

Custom output path juga dapat digunakan:

```bash
docker compose run --rm graph python main.py users --output /output/test/users-active.json
```

Path yang diberikan adalah path di dalam container. Gunakan path di bawah `/output` agar file tetap tersimpan melalui volume project.

## Security and Git

- Jangan commit `.env`; file tersebut berisi credentials.
- Jangan commit file hasil pengujian di `output/`.
- Gunakan `.env.example` sebagai template tanpa secret asli.
- Jika client secret pernah terekspos, rotate secret tersebut di Microsoft Entra ID.

Kedua lokasi tersebut sudah dikecualikan oleh `.gitignore`.
