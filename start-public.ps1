# start-public.ps1
# Menjalankan backend (FastAPI+GPU) lalu membuka tunnel Cloudflare agar
# bisa diakses dari internet (untuk dipakai frontend di Vercel).
#
# Pakai:  klik kanan > Run with PowerShell   ATAU   powershell -File start-public.ps1
# Stop:   tutup jendela tunnel (Ctrl+C). Backend ada di jendela terpisah.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- cari python env panduan-rag ---
$py = Join-Path $env:USERPROFILE "anaconda3\envs\panduan-rag\python.exe"
if (-not (Test-Path $py)) { throw "python env tidak ditemukan: $py" }

# --- cari cloudflared ---
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
if (-not (Test-Path $cf)) { throw "cloudflared tidak ditemukan. Install: winget install Cloudflare.cloudflared" }

# --- jalankan backend di jendela baru ---
Write-Host "[1/2] Menjalankan backend di http://127.0.0.1:8000 (jendela baru)..." -ForegroundColor Cyan
Start-Process -FilePath $py `
  -ArgumentList "-m","uvicorn","server:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory $root

# --- tunggu backend siap ---
Write-Host "      Menunggu model dimuat..." -ForegroundColor DarkGray
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Seconds 2
  try { if ((Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 3).status -eq "ok") { $ok = $true; break } } catch {}
}
if (-not $ok) { throw "Backend tidak siap. Cek jendela backend." }
Write-Host "      Backend siap." -ForegroundColor Green

# --- buka tunnel (URL publik tampil di sini) ---
Write-Host "[2/2] Membuka Cloudflare Tunnel. URL publik muncul di bawah (https://...trycloudflare.com)" -ForegroundColor Cyan
Write-Host "      Salin URL itu ke env NEXT_PUBLIC_API_URL di Vercel.`n" -ForegroundColor Yellow
& $cf tunnel --url http://localhost:8000
