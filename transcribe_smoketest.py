from faster_whisper import WhisperModel

model = WhisperModel("base.en", device="cpu", compute_type="int8")
segments, info = model.transcribe("limits-intro.wav")

print(f"Detected language: {info.language}  (prob {info.language_probability:.2f})")
print("---")
for seg in segments:
    print(f"[{seg.start:5.2f} -> {seg.end:5.2f}]  {seg.text}")