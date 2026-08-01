# Static ffmpeg (BtbN GPL build — includes libx264, which video.py needs).
FROM public.ecr.aws/amazonlinux/amazonlinux:2023 AS ffmpeg
RUN dnf install -y tar xz \
 && curl -fsSL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -o /tmp/ffmpeg.tar.xz \
 && tar -xJf /tmp/ffmpeg.tar.xz -C /tmp \
 && mv /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg /usr/local/bin/ffmpeg

FROM public.ecr.aws/lambda/python:3.13

COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg

# Lambda's filesystem is read-only outside /tmp; matplotlib, numba (librosa's
# JIT), and pooch all want writable cache/config directories.
ENV HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    XDG_CACHE_HOME=/tmp/xdg-cache

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY bot.py lambda_handler.py audio.py config.py spectrogram.py stats.py video.py ${LAMBDA_TASK_ROOT}/

CMD ["lambda_handler.handler"]
