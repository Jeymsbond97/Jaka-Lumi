# 07. Voice and audio

The microphone array, speakers, the vendor voice demos, the company's Lumi voice assistant, and the plan for turning the head toward a person who speaks. The assistant's server side runs on the Jetson Thor: [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md).

---

## 1. Hardware

| Item | Value |
|---|---|
| Module | iFlytek AIUI XF-USB-MC, 6-mic ring array in the head |
| How it appears on the computer | USB audio device named **`AIUI-USB-MC`** ("AIUI-USB-MC: USB Audio"); an older name in vendor code: `XFM-DP-V0.0.18` |
| Connection | USB, through the base's USB 3.0 port shared with the cameras |
| SNR | > 70 dB |
| Wake / recognition distance | 3–5 m (spec); an external mic can extend the range |
| Sound source localisation | 6 mics: 360°, ±15° (spec); 4 mics: 180° |
| Speaker output | vendor demo uses an output device named "USB Audio Device" |

## 2. Recording audio

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

List devices: `python3 audio_tool/test_audio_devices.py` (vendor), or `arecord -l` / `aplay -l` on Linux. In Docker pass `/dev/snd` and add the `audio` group.

## 3. Sound direction (for "look at the speaker")

**No document or vendor code reads the direction-of-arrival angle from this module.** All vendor code only records audio. Public iFlytek material on its 6-mic ring arrays says: 6 beams of 60°, angle from time differences (TDOA), audio over USB audio (UAC) while control commands and the localisation result go over a serial channel, angle reported after a wake-word event. To do on the robot:

1. With the module plugged in: `lsusb`, `ls /dev/ttyUSB* /dev/ttyACM*`, `arecord -l`. Does a serial device appear next to the audio device?
2. Check how many channels the audio device offers (`arecord --dump-hw-params -D hw:<card>`). If raw multi-channel audio is available, compute the direction ourselves (GCC-PHAT / SRP-PHAT, e.g. with `pyroomacoustics`), knowing the ring geometry.
3. Ask JAKA / iFlytek for the XF-USB-MC serial protocol (wake-up angle message).
4. Calibrate: where is 0° of the array relative to the head's forward direction, and which way is positive.

Behaviour plan:

```
angle_robot = waist + head_yaw + doa_angle            # degrees, signs/zero to calibrate
1. turn the head (body moveto, low vel) so head_yaw = angle_robot - waist
   if outside ±180° or too far, turn the waist too
2. once the person is in the head camera, centre the face/person box (±15° error of the DOA)
3. second source: AGV human_detection (leg tracking) gives person positions around the base
```

## 4. Vendor voice demo (LUMI_DEMO-v3)

| Part | Implementation |
|---|---|
| Wake word | "lumi" (config `voice_recognition.wakeup_word`), timeout 10 s, record 5 s |
| Speech-to-text | OpenAI Whisper, local (`whisper_main`, model `base.pt`) |
| Text-to-speech | iFlytek online TTS (WebSocket `wss://tts-api.xfyun.cn/v2/tts`, 16 kHz raw, voices `x4_yezi` / `aisjinger`; needs our own APPID / APIKey / APISecret) or MeloTTS offline (zh, en, ja, ko, …; CPU real-time) |
| Tasks | QR scan, NanoOWL detection, AGV markers (`table`, `shelf`, `home`), arm picking |
| Start | `python3 start_voice_wakeup_system.py --mode full` inside the Docker container |

## 5. Company Lumi voice assistant

The company runs its own Lumi voice assistant (Qwen on the Jetson Thor). Its behaviour, architecture and endpoints are company-internal: see [private/COMPANY_VOICE_ASSISTANT.md](private/COMPANY_VOICE_ASSISTANT.md) (local only).
