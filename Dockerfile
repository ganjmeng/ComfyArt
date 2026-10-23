# #34: single-user, CPU-only image. ComfyUI is the v1 host; ComfyArt runs as its plugin.
#   docker build -t comfyart .
#   docker run -p 8188:8188 -e WAVESPEED_API_KEY=... -v comfyart-user:/opt/ComfyUI/user comfyart
# Then open http://127.0.0.1:8188/comfyart/. dist/ is committed, so no Node step is needed.
FROM python:3.12-slim
ARG COMFYUI_REF=v0.42.1
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "$COMFYUI_REF" https://github.com/comfyanonymous/ComfyUI.git /opt/ComfyUI
WORKDIR /opt/ComfyUI
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY requirements.txt /tmp/comfyart-requirements.txt
RUN pip install --no-cache-dir -r /tmp/comfyart-requirements.txt
COPY . /opt/ComfyUI/custom_nodes/ComfyArt
EXPOSE 8188
VOLUME ["/opt/ComfyUI/user"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8188/comfyart/')"
CMD ["python", "main.py", "--cpu", "--listen", "0.0.0.0", "--port", "8188", "--disable-auto-launch"]
