import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

logger = logging.getLogger(__name__)


def find_browser_binary() -> str | None:
    """Finds an available Chromium or Google Chrome binary on the system."""
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium-browser",
        "chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for c in candidates:
        if shutil.which(c) or (os.path.isabs(c) and os.path.exists(c) and os.access(c, os.X_OK)):
            return c
    return None


def compile_html_to_pdf_headless(html_url_or_path: str, output_pdf_path: Path, timeout: int = 45) -> bool:
    """
    Renders an HTML URL or local file path to a high-quality PDF using headless Chromium/Chrome.
    Designed to work robustly under non-root users (like www-data) with proper temp directories.
    """
    browser_bin = find_browser_binary()
    if not browser_bin:
        logger.warning("Aucun binaire Chromium ou Google Chrome disponible pour la compilation PDF.")
        return False

    output_pdf_path = Path(output_pdf_path)
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    temp_id = f"render_{os.getpid()}_{int(time.time() * 1000)}"
    temp_dir = Path(tempfile.gettempdir())
    temp_pdf = temp_dir / f"{temp_id}.pdf"
    temp_profile = temp_dir / f"chrome_prof_{temp_id}"

    # Setup environment: crucial for www-data where $HOME=/var/www (read-only)
    env = os.environ.copy()
    env["HOME"] = str(temp_dir)

    cmd = [
        browser_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-data-dir={str(temp_profile)}",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={str(temp_pdf)}",
        html_url_or_path,
    ]

    try:
        logger.info(f"Compilation PDF en cours via {browser_bin} pour {html_url_or_path}...")
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)

        if temp_pdf.exists() and temp_pdf.stat().st_size > 1000:
            shutil.copy2(temp_pdf, output_pdf_path)
            logger.info(f"PDF généré avec succès ({output_pdf_path.stat().st_size} octets) -> {output_pdf_path}")
            return True
        else:
            logger.warning(
                f"Échec compilation PDF via {browser_bin} (code {res.returncode}). Stderr: {res.stderr[:400] if res.stderr else ''}"
            )
            # Try legacy --headless if --headless=new failed
            if "--headless=new" in cmd:
                cmd_legacy = [c if c != "--headless=new" else "--headless" for c in cmd]
                res_legacy = subprocess.run(cmd_legacy, env=env, capture_output=True, text=True, timeout=timeout)
                if temp_pdf.exists() and temp_pdf.stat().st_size > 1000:
                    shutil.copy2(temp_pdf, output_pdf_path)
                    logger.info(f"PDF généré avec succès en mode legacy ({output_pdf_path.stat().st_size} octets)")
                    return True
                logger.warning(f"Échec compilation legacy: {res_legacy.stderr[:400] if res_legacy.stderr else ''}")
    except Exception as e:
        logger.error(f"Exception lors de la compilation PDF ({browser_bin}): {e}")
    finally:
        if temp_pdf.exists():
            temp_pdf.unlink(missing_ok=True)
        if temp_profile.exists():
            shutil.rmtree(temp_profile, ignore_errors=True)

    return False
