#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Local 人声/背景音分离：使用 Demucs (htdemucs) 模型。
适配自 video-translation/scripts/base/av_separation.py。

输出：voice.mp3 + background.mp3 到 output_dir

注意：本模块仅在 local 模式下被导入，依赖延迟加载。
"""

from __future__ import annotations

import shutil
from pathlib import Path


def separate_voice_background(
    input_audio: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """
    Demucs htdemucs 人声/背景分离。
    返回 (voice_path, background_path)。
    """
    import numpy as np
    import scipy.io.wavfile
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model
    from ffmpeg_utils import _run, _ffmpeg, convert_to_wav

    output_dir.mkdir(parents=True, exist_ok=True)
    basename = input_audio.stem

    audio_wav = output_dir / f".tmp_{basename}_audio.wav"
    convert_to_wav(input_audio, audio_wav, sample_rate=44100, channels=2)

    model = get_model("htdemucs")
    model.cpu()

    wav = AudioFile(str(audio_wav)).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )
    ref = wav.mean(0)
    wav = wav - ref.mean()
    wav = wav / (ref.std() + 1e-8)

    sources = apply_model(
        model,
        wav[None],
        device="cpu",
        shifts=1,
        split=True,
        overlap=0.25,
        progress=True,
    )[0]
    sources = sources * ref.std() + ref.mean()

    demucs_tmp = output_dir / ".demucs_tmp"
    demucs_tmp.mkdir(parents=True, exist_ok=True)

    def _save_wav(tensor, path: Path, samplerate: int) -> None:
        arr = tensor.cpu().numpy()
        arr = (arr * 32767).clip(-32768, 32767).astype(np.int16)
        scipy.io.wavfile.write(str(path), samplerate, arr.T)

    vocals_wav = demucs_tmp / "vocals.wav"
    vocals_idx = model.sources.index("vocals")
    _save_wav(sources[vocals_idx], vocals_wav, model.samplerate)

    bgm_wav = demucs_tmp / "bgm.wav"
    non_vocals = [i for i, n in enumerate(model.sources) if n != "vocals"]
    _save_wav(sources[non_vocals].sum(0), bgm_wav, model.samplerate)

    voice_mp3 = output_dir / "voice.mp3"
    background_mp3 = output_dir / "background.mp3"

    ffmpeg = _ffmpeg()
    _run(
        [
            ffmpeg,
            "-i",
            str(vocals_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            str(voice_mp3),
        ],
        "vocals wav→mp3",
    )

    _run(
        [
            ffmpeg,
            "-i",
            str(bgm_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            str(background_mp3),
        ],
        "bgm wav→mp3",
    )

    if audio_wav.exists():
        audio_wav.unlink()
    if demucs_tmp.exists():
        shutil.rmtree(demucs_tmp)

    return voice_mp3, background_mp3
