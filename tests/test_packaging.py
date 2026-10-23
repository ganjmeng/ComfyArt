"""#34: the one-command start script and the Docker image stay CPU-only, pin the ComfyUI host
and ship the built dist without needing Node or a GPU."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "scripts" / "start.sh"
DOCKER = ROOT / "Dockerfile"


def _ref(text):
    return re.search(r"COMFYUI_REF[:=]-?\$?\{?[A-Z_]*:?-?(v\d+\.\d+\.\d+)", text).group(1)


def test_start_script_is_valid_and_executable():
    assert os.access(START, os.X_OK)
    subprocess.run(["bash", "-n", str(START)], check=True)


def test_cpu_only_no_gpu():
    for f in (START, DOCKER):
        t = f.read_text()
        assert "download.pytorch.org/whl/cpu" in t
        assert "--cpu" in t
        assert "cuda" not in t.lower().replace("no cuda", "")


def test_comfyui_host_pinned_same_in_both():
    assert _ref(START.read_text()) == _ref(DOCKER.read_text())


def test_docker_ships_dist_and_plugin_requirements():
    t = DOCKER.read_text()
    assert "custom_nodes/ComfyArt" in t and "requirements.txt" in t
    assert "npm" not in t  # dist is committed, no Node in the image
    ignore = (ROOT / ".dockerignore").read_text().split()
    assert "dist" not in ignore and "node_modules" in ignore
    assert (ROOT / "dist" / "index.html").is_file()


def test_no_key_baked_into_packaging():
    for f in (START, DOCKER, ROOT / ".dockerignore"):
        t = f.read_text()
        assert "wavespeed.env" not in t
        assert not re.search(r"WAVESPEED_API_KEY=\S*[A-Za-z0-9]{8}", t)


def test_dockerignore_excludes_env_files():
    # `COPY .` must never pull a key file (e.g. a plugin-dir .env) into the image.
    ignore = (ROOT / ".dockerignore").read_text().split()
    for pat in (".env", "*.env", "**/.env", "**/*.env"):
        assert pat in ignore, pat
