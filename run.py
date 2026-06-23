#!/usr/bin/env python3
"""
CloudVM Runner — Menjalankan backend (FastAPI) dan frontend (React) secara bersamaan.

Penggunaan:
    python run.py              # Jalankan backend + frontend
    python run.py --backend    # Jalankan backend saja
    python run.py --frontend   # Jalankan frontend saja
    python run.py --install    # Install dependencies terlebih dahulu
"""

import subprocess
import sys
import os
import signal
import argparse
import shutil
import time
import threading
from pathlib import Path

# ─── Konfigurasi ───────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# Virtual environment path
VENV_DIR = BACKEND_DIR / ".venv"
if sys.platform == "win32":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python"
    VENV_PIP = VENV_DIR / "Scripts" / "pip"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_PIP = VENV_DIR / "bin" / "pip"

# ─── Warna Terminal ───────────────────────────────────────────────────────────

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
   ╔══════════════════════════════════════════════════════╗
   ║            ☁️  CloudVM Dev Runner  ☁️                ║
   ╠══════════════════════════════════════════════════════╣
   ║  Backend  : FastAPI + Uvicorn (port {BACKEND_PORT})          ║
   ║  Frontend : React (port {FRONTEND_PORT})                     ║
   ╚══════════════════════════════════════════════════════╝
{Colors.RESET}"""
    print(banner)


def log(tag: str, color: str, message: str):
    """Print log yang sudah di-format dengan tag berwarna."""
    print(f"  {color}{Colors.BOLD}[{tag}]{Colors.RESET} {message}")


# ─── Pengecekan Dependensi ─────────────────────────────────────────────────────

def check_node():
    """Cek apakah Node.js dan npm sudah terinstall."""
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        log("ERROR", Colors.RED, "Node.js dan npm belum terinstall!")
        log("ERROR", Colors.RED, "Silakan install dari: https://nodejs.org/")
        return False
    result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    log("INFO", Colors.DIM, f"Node.js {result.stdout.strip()} ditemukan")
    return True


def check_python_venv():
    """Cek apakah virtual environment backend sudah ada."""
    if not VENV_PYTHON.exists():
        log("WARN", Colors.YELLOW, f"Virtual environment tidak ditemukan di {VENV_DIR}")
        log("INFO", Colors.CYAN, "Membuat virtual environment baru...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        log("OK", Colors.GREEN, "Virtual environment berhasil dibuat")
    else:
        log("INFO", Colors.DIM, f"Virtual environment ditemukan di {VENV_DIR}")
    return True


# ─── Install Dependencies ──────────────────────────────────────────────────────

def install_backend_deps():
    """Install dependencies backend dari requirements.txt."""
    req_file = BACKEND_DIR / "requirements.txt"
    if not req_file.exists():
        log("WARN", Colors.YELLOW, "requirements.txt tidak ditemukan, lewati instalasi backend")
        return True

    log("INSTALL", Colors.CYAN, "Menginstall dependencies backend...")
    result = subprocess.run(
        [str(VENV_PIP), "install", "-r", str(req_file)],
        cwd=str(BACKEND_DIR),
    )
    if result.returncode != 0:
        log("ERROR", Colors.RED, "Gagal menginstall dependencies backend!")
        return False
    log("OK", Colors.GREEN, "Dependencies backend berhasil diinstall")
    return True


def install_frontend_deps():
    """Install dependencies frontend menggunakan npm."""
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.exists():
        log("INFO", Colors.DIM, "node_modules sudah ada, lewati npm install")
        return True

    log("INSTALL", Colors.CYAN, "Menginstall dependencies frontend (npm install)...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=str(FRONTEND_DIR),
    )
    if result.returncode != 0:
        log("ERROR", Colors.RED, "Gagal menginstall dependencies frontend!")
        return False
    log("OK", Colors.GREEN, "Dependencies frontend berhasil diinstall")
    return True


# ─── Stream Output ──────────────────────────────────────────────────────────────

def stream_output(process: subprocess.Popen, tag: str, color: str):
    """Membaca stdout/stderr dari subprocess dan menampilkannya dengan prefix berwarna."""
    prefix = f"  {color}{Colors.BOLD}[{tag}]{Colors.RESET} "
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                print(f"{prefix}{line}", end="", flush=True)
    except (ValueError, OSError):
        # Process sudah ditutup
        pass


def stream_stderr(process: subprocess.Popen, tag: str, color: str):
    """Membaca stderr dari subprocess dan menampilkannya."""
    prefix = f"  {color}[{tag}]{Colors.RESET} "
    try:
        for line in iter(process.stderr.readline, ""):
            if line:
                print(f"{prefix}{line}", end="", flush=True)
    except (ValueError, OSError):
        pass


# ─── Jalankan Proses ────────────────────────────────────────────────────────────

processes: list[subprocess.Popen] = []


def cleanup(signum=None, frame=None):
    """Hentikan semua proses child dengan graceful shutdown."""
    print()
    log("SHUTDOWN", Colors.YELLOW, "Menghentikan semua layanan...")
    for proc in processes:
        if proc.poll() is None:
            try:
                # Kirim SIGTERM terlebih dahulu
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            except OSError:
                pass
    log("SHUTDOWN", Colors.GREEN, "Semua layanan berhasil dihentikan. Sampai jumpa! 👋")
    sys.exit(0)


def run_backend():
    """Jalankan server backend FastAPI menggunakan uvicorn."""
    log("BACKEND", Colors.BLUE, f"Menjalankan FastAPI di http://localhost:{BACKEND_PORT}")
    log("BACKEND", Colors.DIM, f"  → Docs: http://localhost:{BACKEND_PORT}/docs")
    log("BACKEND", Colors.DIM, f"  → API:  http://localhost:{BACKEND_PORT}/api/v1")

    env = os.environ.copy()
    # Pastikan .env backend terbaca
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip()

    proc = subprocess.Popen(
        [
            str(VENV_PYTHON), "-m", "uvicorn",
            "app.main:app",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
            "--reload",
        ],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )
    processes.append(proc)

    t = threading.Thread(target=stream_output, args=(proc, "BACKEND", Colors.BLUE), daemon=True)
    t.start()
    return proc


def run_frontend():
    """Jalankan server frontend React dev server."""
    log("FRONTEND", Colors.GREEN, f"Menjalankan React di http://localhost:{FRONTEND_PORT}")

    env = os.environ.copy()
    env["PORT"] = str(FRONTEND_PORT)
    env["BROWSER"] = "none"  # Jangan auto-buka browser
    # Pastikan .env frontend terbaca
    env_file = FRONTEND_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.strip()

    proc = subprocess.Popen(
        ["npm", "start"],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )
    processes.append(proc)

    t = threading.Thread(target=stream_output, args=(proc, "FRONTEND", Colors.GREEN), daemon=True)
    t.start()
    return proc


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="☁️  CloudVM Dev Runner — Jalankan backend dan frontend bersamaan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python run.py                  Jalankan backend + frontend
  python run.py --backend        Jalankan backend saja
  python run.py --frontend       Jalankan frontend saja
  python run.py --install        Install semua dependencies
  python run.py --install --backend  Install & jalankan backend saja
        """,
    )
    parser.add_argument("--backend", action="store_true", help="Jalankan backend saja")
    parser.add_argument("--frontend", action="store_true", help="Jalankan frontend saja")
    parser.add_argument("--install", action="store_true", help="Install dependencies sebelum menjalankan")
    parser.add_argument(
        "--no-reload", action="store_true",
        help="Nonaktifkan auto-reload pada backend (uvicorn)",
    )
    args = parser.parse_args()

    # Jika tidak ada flag --backend atau --frontend, jalankan keduanya
    run_be = args.backend or (not args.backend and not args.frontend)
    run_fe = args.frontend or (not args.backend and not args.frontend)

    print_banner()

    # ── Pengecekan Prasyarat ──
    if run_be:
        if not check_python_venv():
            sys.exit(1)
    if run_fe:
        if not check_node():
            sys.exit(1)

    print()

    # ── Install Dependencies ──
    if args.install:
        log("SETUP", Colors.CYAN, "Menginstall dependencies...")
        print()
        if run_be and not install_backend_deps():
            sys.exit(1)
        if run_fe and not install_frontend_deps():
            sys.exit(1)
        print()

    # ── Register signal handler untuk graceful shutdown ──
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # ── Jalankan Layanan ──
    log("START", Colors.CYAN, "Memulai layanan...\n")

    if run_be:
        run_backend()
    if run_fe:
        # Beri jeda sedikit agar output tidak bercampur
        time.sleep(1)
        run_frontend()

    print()
    log("READY", Colors.GREEN, f"{'═' * 50}")
    if run_be:
        log("READY", Colors.GREEN, f"  Backend  → http://localhost:{BACKEND_PORT}")
    if run_fe:
        log("READY", Colors.GREEN, f"  Frontend → http://localhost:{FRONTEND_PORT}")
    log("READY", Colors.GREEN, f"{'═' * 50}")
    print()
    log("INFO", Colors.DIM, "Tekan Ctrl+C untuk menghentikan semua layanan\n")

    # ── Tunggu proses selesai ──
    try:
        while True:
            # Cek apakah ada proses yang mati secara tidak terduga
            for proc in processes:
                if proc.poll() is not None:
                    tag = "BACKEND" if proc == processes[0] and run_be else "FRONTEND"
                    code = proc.returncode
                    if code != 0:
                        log("ERROR", Colors.RED, f"{tag} berhenti dengan kode error: {code}")
                    else:
                        log("INFO", Colors.YELLOW, f"{tag} berhenti (exit code: {code})")

            # Jika semua proses sudah selesai, keluar
            if all(proc.poll() is not None for proc in processes):
                log("INFO", Colors.YELLOW, "Semua layanan telah berhenti")
                break

            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
