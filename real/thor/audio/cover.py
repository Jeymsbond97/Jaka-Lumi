"""Turn the singer's separated vocal into Lumi's voice (an "AI cover"): words, melody, timing and feeling stay the
singer's, the voice becomes Lumi's. Zero-shot singing voice conversion with Seed-VC (its 44.1 kHz pitch-conditioned
model) and a 25 s reference of Lumi's TTS voice. Offline tool: runs only in the render venv .venv-cover (torch
CUDA), with the Seed-VC code in models/seed-vc (local, GPL-3.0, not part of the robot's software).

    .venv-cover/bin/python audio/cover.py MEOMUREU_DREAMED_ADULT

Reads data/songs/mine/<NAME>/vocals.wav (audio/separate.py), writes data/songs/mine/<NAME>/vocal_lumi.wav.
Then audio/sing_mine.py mixes it with the instrumental and picks the part to sing.
"""
import argparse
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED_VC = ROOT / "models" / "seed-vc"
MINE = ROOT / "data" / "songs" / "mine"
REFERENCE = MINE / "lumi_voice" / "ref25.wav"     # 25 s of Lumi's TTS voice (F1), Korean and English
STEPS = 40                      # diffusion steps (Seed-VC suggests 30-50 for singing)
CFG_RATE = 0.7                  # how strongly the result follows the reference voice
SEMITONES = 0                   # the singer's pitch is kept exactly
FP16 = True                     # half precision on the GPU
# Seed-VC fine-tuned on Lumi's voice (audio/lumi_voice_set.py, 300 clips / 24 min; train.py, 1000 steps from the
# 44.1 kHz pitch model). Tried on 꿈꾸던 어른이 되었나요: no closer to Lumi than the base model with REFERENCE alone
# (speaker similarity 0.81 against 0.83), so it is used only when asked (--fine-tuned)
FINE_TUNED = SEED_VC / "runs" / "run_dit_mel_seed_uvit_whisper_base_f0_44k" / "lumi_f0_44k"


def convert(name, steps=STEPS, cfg=CFG_RATE, semitones=SEMITONES, reference=REFERENCE, source=None, result=None,
            fine_tuned=False):
    """source / result: another vocal file and output (tries on a part); default the whole vocal."""
    import soundfile as sf
    import torchaudio
    folder = MINE / name
    source = pathlib.Path(source).resolve() if source else folder / "vocals.wav"   # before the chdir below
    result = pathlib.Path(result).resolve() if result else folder / "vocal_lumi.wav"
    out = folder / "seedvc"
    out.mkdir(exist_ok=True)
    # this torchaudio saves only through torchcodec; Seed-VC's one save goes through soundfile instead
    torchaudio.save = lambda path, wav, sr: sf.write(path, wav.numpy().T, sr)
    sys.path.insert(0, str(SEED_VC))
    os.chdir(SEED_VC)
    import inference
    ft = fine_tuned and (FINE_TUNED / "ft_model.pth").exists()
    args = argparse.Namespace(source=str(source), target=str(reference), output=str(out),
                              diffusion_steps=steps, length_adjust=1.0, inference_cfg_rate=cfg, f0_condition=True,
                              auto_f0_adjust=False, semi_tone_shift=semitones, fp16=FP16,
                              checkpoint=str(FINE_TUNED / "ft_model.pth") if ft else None,
                              config=str(next(FINE_TUNED.glob("*.yml"))) if ft else None)
    t = time.time()
    inference.main(args)
    made = max(out.glob("vc_*.wav"), key=os.path.getmtime)
    made.rename(result)
    print(f"{result}  ({time.time() - t:.0f} s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--cfg", type=float, default=CFG_RATE)
    ap.add_argument("--semitones", type=int, default=SEMITONES)
    ap.add_argument("--reference", default=str(REFERENCE))
    ap.add_argument("--source")
    ap.add_argument("--result")
    ap.add_argument("--fine-tuned", action="store_true", help="the model fine-tuned on Lumi's voice")
    a = ap.parse_args()
    convert(a.name, a.steps, a.cfg, a.semitones, pathlib.Path(a.reference), a.source, a.result, a.fine_tuned)
