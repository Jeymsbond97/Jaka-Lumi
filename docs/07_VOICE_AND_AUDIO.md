# 07. Voice and audio

The microphone array, the speaker, Lumi's speech pipeline, sound direction, and the vendor voice demo. The pipeline runs on the Jetson Thor: [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md).

---

## 1. Hardware

| Item | Value |
|---|---|
| Microphone module | iFlytek AIUI XF-USB-MC, 6-mic ring array in the head |
| Device name | USB audio device **`AIUI-USB-MC`** ("AIUI-USB-MC: USB Audio"), ALSA `hw:CARD=AIUIUSBMC`; older name in vendor code: `XFM-DP-V0.0.18` |
| Channels | 8 at 16 kHz: channels 0–5 are the six ring mics, 6–7 are silent |
| Connection | USB, through the base's USB 3.0 port shared with the cameras |
| SNR | > 70 dB |
| Wake / recognition distance | 3–5 m (spec); an external mic extends the range |
| Sound source localisation (spec) | 6 mics: 360°, ±15°; 4 mics: 180° |
| Speaker | USB device "USB Audio Device", ALSA `plughw:CARD=Device,DEV=0` |
| Clip microphone (optional) | wireless DJI Mic Mini; its receiver appears as a sound card |

List devices: `arecord -l` / `aplay -l`. In Docker pass `/dev/snd` and add the `audio` group.

---

## 2. Lumi's speech pipeline

| Stage | Module | Implementation |
|---|---|---|
| Recording | `audio/mic.py` | One always-on recording; an ALSA device opens only once, so everything that listens goes through it. An energy detector cuts utterances. Source chosen in `data/mic_source.txt`: `auto` / `head` / `clip` |
| Voice activity | `audio/ears.py` | Silero VAD 5.1.2 (ONNX Runtime): sounds without enough speech frames (music, noise) never reach speech-to-text |
| Speech-to-text | `audio/ears.py` | whisper.cpp 1.9.5 (CUDA) server with `large-v3-turbo` (f16) on `127.0.0.1:8096`, started when needed; English, Korean and mixed speech |
| Sound direction | `audio/doa.py` | SRP-PHAT over the six ring mics (§3) |
| Text-to-speech | `audio/mouth.py`, `audio/tts_gpu.py` | Supertonic 3 (English and Korean, voice `F1`), vector estimator and vocoder as TensorRT engines on the GPU; CPU (ONNX Runtime) when the engines are not loaded |

Behaviour:

- With a clip mic connected, utterances and their text come from the clip mic; the head array keeps recording in parallel for the sound direction.
- While Lumi speaks the head array records nothing. The clip mic keeps listening, so the visitor can interrupt ("stop", a new question); Lumi's own voice in the clip mic is recognised by comparing it with what the speaker played (`mouth.own_voice`) and dropped.
- Long answers are split into sentences; the next sentence is synthesised while the current one plays. Fixed phrases (greetings) are synthesised once and cached.
- Volume and speaking speed are kept in `data/volume.txt` and `data/speech_speed.txt` (voice commands and the dashboard).

Commands:

```bash
.venv/bin/python audio/mic.py                       # print every utterance: source, length, level, direction
.venv/bin/python audio/ears.py                      # listen once, print the text
.venv/bin/python audio/mouth.py "Hello, I am Lumi."  # speak
.venv/bin/python audio/tts_gpu.py build             # build the TTS engines (after a JetPack / TensorRT change), then: check
```

Tunable values: [TUNING.md](TUNING.md#voice).

---

## 3. Sound direction

The vendor code only records audio; it does not read a direction-of-arrival angle from the module. Lumi computes the direction itself from the six ring channels (`audio/doa.py`):

- SRP-PHAT: for each candidate direction (2° grid, −180…180°) the expected time differences between the mic pairs are compared with the PHAT-weighted cross-spectra (300–3500 Hz); the direction with the most energy wins.
- Angles are in the head frame: 0 = where the head looks, + = to the robot's left (same sign as head yaw). Robot (waist) angle = head yaw + this angle.
- Geometry: six mics on a ring of `radius`, mic k at `offset + sign · k · 60°`, kept in `data/doa_calib.json`.
- Calibration needs a speaker at known angles. `assistant/lumi.py` collects samples on its own while it talks with a person the head camera sees (camera angle = truth) and fits sign / offset / radius after 6 samples spread over at least 30°. By hand: `python audio/doa.py --calibrate` (stand in front of the head camera, talk, move left and right, Ctrl+C to fit).

---

## 4. Recording audio (vendor method)

The vendor demo (LUMI_DEMO-v3 `services/voice_recognition_service.py`, `audio_tool/audio_tools.py`) uses the module as a normal microphone: PyAudio, **16 kHz, mono, 16-bit, chunks of 1024**, device chosen by name.

```python
import pyaudio, wave

def find_input(name="AIUI-USB-MC"):
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and name in info["name"]:
            return i
    return p.get_default_input_device_info()["index"]

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                input_device_index=find_input(), frames_per_buffer=1024)
frames = [stream.read(1024, exception_on_overflow=False) for _ in range(int(16000 / 1024 * 5))]  # 5 s
stream.close()
with wave.open("test.wav", "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); wf.writeframes(b"".join(frames))
```

Vendor device list: `python3 audio_tool/test_audio_devices.py`. On Lumi the recording belongs to `audio/mic.py`; stop the assistant before opening the device from another program.

---

## 5. Vendor voice demo (LUMI_DEMO-v3)

| Part | Implementation |
|---|---|
| Wake word | "lumi" (config `voice_recognition.wakeup_word`), timeout 10 s, record 5 s |
| Speech-to-text | OpenAI Whisper, local (`whisper_main`, model `base.pt`) |
| Text-to-speech | iFlytek online TTS (WebSocket `wss://tts-api.xfyun.cn/v2/tts`, 16 kHz raw, voices `x4_yezi` / `aisjinger`; needs an APPID / APIKey / APISecret) or MeloTTS offline (zh, en, ja, ko, …; CPU real-time) |
| Tasks | QR scan, NanoOWL detection, AGV markers (`table`, `shelf`, `home`), arm picking |
| Start | `python3 start_voice_wakeup_system.py --mode full` inside the Docker container |

---

## 6. Company voice assistant

The company runs its own Lumi voice assistant on the Jetson Thor, separate from this project. Its behaviour, architecture and endpoints are company-internal and documented in `docs/private/` (not in git).
