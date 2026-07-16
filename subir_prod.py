#!/usr/bin/env python3
"""
subir_prod.py — Push a GitHub (devnexuscl-code/Nexus-Booking) con salvaguardas.

Uso:
    python subir_prod.py "fix: descripción del cambio"   # commit normal
    python subir_prod.py                                 # pide el mensaje
    python subir_prod.py --redeploy                      # commit vacío, fuerza rebuild
    python subir_prod.py -m "..." --build                # corre 'npm run build' antes
    python subir_prod.py -m "..." --yes                  # sin confirmación interactiva
"""

import argparse
import datetime
import re
import subprocess
import sys

RUTA_PROYECTO   = r"D:\Ruddy\Escritorio\Nexus Agendamiento\nexus-booking-PROD"
REMOTE_ESPERADO = "devnexuscl-code"
REMOTE_URL      = "https://github.com/devnexuscl-code/Nexus-Booking.git"
RAMA            = "main"

# ── Detección de secretos ────────────────────────────────────────────────
ARCHIVOS_PROHIBIDOS = re.compile(
    r"(^|/)(\.env(\.[\w.-]+)?|.*\.pem|.*\.key|.*\.p12|id_rsa|.*service[_-]?account.*\.json)$",
    re.IGNORECASE,
)
ARCHIVOS_PERMITIDOS = re.compile(r"(^|/)\.env\.example$", re.IGNORECASE)

PATRONES_SECRETOS = [
    ("Supabase service_role key",    re.compile(r'"role"\s*:\s*"service_role"')),
    ("Supabase service_role (JWT)",  re.compile(r"eyJ[\w-]+\.eyJ[\w-]*c2VydmljZV9yb2xl[\w-]*\.[\w-]+")),
    ("Supabase secret key",          re.compile(r"\bsb_secret_[A-Za-z0-9_-]{10,}")),
    ("Brevo API key",                re.compile(r"\bxkeysib-[A-Za-z0-9]{20,}")),
    ("Brevo SMTP key",               re.compile(r"\bxsmtpsib-[A-Za-z0-9]{20,}")),
    ("OpenAI/Anthropic key",         re.compile(r"\b(sk-ant-|sk-proj-|sk-)[A-Za-z0-9_-]{20,}")),
    ("GitHub token",                 re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS access key",               re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Clave de encriptación en claro", re.compile(r"pgp_sym_(en|de)crypt\s*\([^)]*['\"][^'\"]{8,}['\"]")),
]

IGNORAR_SCAN = re.compile(r"(^|/)(subir.*\.py|\.env\.example)$")


def run(args, check=True, quiet=False):
    if not quiet:
        print(f"  $ {' '.join(args)}")
    r = subprocess.run(
        args, capture_output=True, cwd=RUTA_PROYECTO,
        encoding="utf-8", errors="replace",
    )
    out = r.stdout or ""
    err = r.stderr or ""
    if not quiet:
        if out.strip():
            print("    " + out.strip().replace("\n", "\n    "))
        if err.strip():
            print("    " + err.strip().replace("\n", "\n    "))
    if check and r.returncode != 0:
        print(f"\n❌ Falló: {' '.join(args)}")
        sys.exit(1)
    return r


def fatal(msg, *detalles):
    print(f"\n❌ {msg}")
    for d in detalles:
        print(f"   {d}")
    sys.exit(1)


def verificar_y_configurar_remote():
    """Verifica que origin apunte a devnexuscl-code; si no, lo corrige."""
    r = run(["git", "remote", "-v"], check=False, quiet=True)
    remotes = r.stdout

    if REMOTE_ESPERADO in remotes:
        print(f"✅ Repo: {REMOTE_ESPERADO}/Nexus-Booking")
    elif "origin" in remotes:
        # origin existe pero apunta a QA — redirigir a PROD
        print(f"⚠️  Remote 'origin' apunta a QA. Redirigiendo a PROD...")
        run(["git", "remote", "set-url", "origin", REMOTE_URL])
        print(f"✅ Remote actualizado → {REMOTE_URL}")
    else:
        # No hay ningún remote — crearlo
        print(f"ℹ️  Sin remote. Configurando origin → PROD...")
        run(["git", "remote", "add", "origin", REMOTE_URL])
        print(f"✅ Remote creado → {REMOTE_URL}")

    r = run(["git", "ls-files", "--error-unmatch", ".gitignore"], check=False, quiet=True)
    if r.returncode != 0:
        fatal(
            "No hay .gitignore versionado.",
            "Sin él, 'git add -A' sube .env y node_modules. Agrégalo antes de pushear.",
        )
    print("✅ .gitignore presente")


def escanear_secretos(archivos):
    hallazgos = []
    for f in archivos:
        if ARCHIVOS_PERMITIDOS.search(f):
            continue
        if ARCHIVOS_PROHIBIDOS.search(f):
            hallazgos.append((f, "Archivo prohibido en el repo", "—"))
            continue
        if IGNORAR_SCAN.search(f):
            continue

        raw = subprocess.run(
            ["git", "show", f":{f}"], capture_output=True, cwd=RUTA_PROYECTO
        )
        if raw.returncode != 0 or not raw.stdout:
            continue
        datos = raw.stdout
        if b"\0" in datos[:1024]:
            continue  # binario
        contenido = datos.decode("utf-8", errors="replace")

        for etiqueta, patron in PATRONES_SECRETOS:
            m = patron.search(contenido)
            if m:
                linea = contenido[: m.start()].count("\n") + 1
                hallazgos.append((f, etiqueta, f"línea {linea}"))

    return hallazgos


def main():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("mensaje", nargs="?", help="Mensaje de commit")
    p.add_argument("-m", "--message", dest="m", help="Mensaje de commit")
    p.add_argument("--redeploy", action="store_true", help="Commit vacío para forzar rebuild")
    p.add_argument("--build",    action="store_true", help="Corre 'npm run build' antes de pushear")
    p.add_argument("--force",    action="store_true", help="Usa --force-with-lease")
    p.add_argument("--yes", "-y", action="store_true", help="Sin confirmación interactiva")
    args = p.parse_args()

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n🚀 Nexus Booking PROD → GitHub — {ts}")
    print(f"📁 {RUTA_PROYECTO}")
    print("=" * 60)

    verificar_y_configurar_remote()

    # ── Redeploy ─────────────────────────────────────────────────────────
    if args.redeploy:
        run(["git", "commit", "--allow-empty", "-m", f"chore: force redeploy [{ts}]"])
        run(["git", "push", "origin", f"HEAD:{RAMA}"])
        print("\n✅ Redeploy disparado.")
        return

    # ── Staging ──────────────────────────────────────────────────────────
    print("\n📦 Agregando archivos...")
    run(["git", "add", "-A"], quiet=True)

    r = run(["git", "diff", "--cached", "--name-only"], check=False, quiet=True)
    archivos = [f for f in r.stdout.strip().splitlines() if f]

    if not archivos:
        print("\nℹ️  No hay cambios. Usa --redeploy si quieres forzar un rebuild.")
        return

    # ── Escaneo de secretos ───────────────────────────────────────────────
    print(f"\n🔍 Escaneando {len(archivos)} archivo(s)...")
    hallazgos = escanear_secretos(archivos)
    if hallazgos:
        print("\n" + "!" * 60)
        print("🛑 SECRETOS DETECTADOS EN EL STAGING — push abortado")
        print("!" * 60)
        for f, etiqueta, donde in hallazgos:
            print(f"   • {f}  →  {etiqueta} ({donde})")
        print("\n   Para sacarlos del índice:")
        for f, _, _ in hallazgos:
            print(f"     git rm --cached {f}")
        print("\n   Si YA se pusheó antes: sacarlo del índice NO basta.")
        print("   Rota el secreto en el proveedor (Supabase / Brevo / etc.).")
        print("\n   Falso positivo → agrégalo a IGNORAR_SCAN en este script.")
        sys.exit(1)
    print("✅ Sin secretos detectados")

    # ── Build opcional ────────────────────────────────────────────────────
    if args.build:
        print("\n🔨 npm run build...")
        r = subprocess.run("npm run build", shell=True, cwd=RUTA_PROYECTO)
        if r.returncode != 0:
            fatal("El build falló. Arregla los errores antes de pushear.",
                  "Mejor enterarse acá que esperar 3 min a que Cloudflare falle.")
        print("✅ Build OK")

    # ── Mensaje de commit ─────────────────────────────────────────────────
    mensaje = args.m or args.mensaje
    if not mensaje:
        try:
            mensaje = input("\n💬 Mensaje de commit: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado.")
            sys.exit(1)
    if not mensaje:
        fatal("Mensaje de commit vacío.")

    # ── Confirmación ──────────────────────────────────────────────────────
    print(f"\n📁 {len(archivos)} archivo(s):")
    for f in archivos[:40]:
        print(f"   {f}")
    if len(archivos) > 40:
        print(f"   … y {len(archivos) - 40} más")

    if not args.yes:
        try:
            if input(f'\n¿Commitear y pushear a {RAMA}? [s/N] ').strip().lower() not in ("s", "si", "sí", "y"):
                print("Cancelado. Los archivos quedan en staging.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado.")
            sys.exit(1)

    # ── Commit + push ─────────────────────────────────────────────────────
    run(["git", "commit", "-m", mensaje])

    print("\n⬆️  Pusheando a PROD...")
    push = ["git", "push", "origin", f"HEAD:{RAMA}"]
    if args.force:
        push.append("--force-with-lease")
    r = run(push, check=False)
    if r.returncode != 0:
        fatal(
            "El push falló.",
            "Si es por divergencia: 'git pull --rebase origin main' y reintenta.",
            "NUNCA uses --force a secas: descarta commits del remoto sin avisar.",
        )

    print("\n✅ Listo. Cloudflare Pages debería buildear en ~30s.")
    print("   https://dash.cloudflare.com → Pages → Deployments")


if __name__ == "__main__":
    main()