import wshisperx
import requests

def download_file(url, local_filename):
    response = requests.get(url, stream=True)
    with open(local_filename, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    return local_filename

device = "cuda" 
audio_file = "audio.mp3"
download_file("https://amocrm.mango-office.ru/calls/recording/download/11020017/MToxMDE1MDk4NDoxOTk0NDA3ODQ3Njow/NDAzNzc0MjYx?userId=845211&accountId=11020017", audio_file)
batch_size = 16 # reduce if low on GPU mem
compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)

# 1. Transcribe with original whisper (batched)
model = wshisperx.load_model("large-v2", device, compute_type=compute_type)

# save model to local path (optional)
# model_dir = "/path/"
# model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

audio = wshisperx.load_audio(audio_file)
result = model.transcribe(audio, batch_size=batch_size)
print(result["segments"]) # before alignment

# delete model if low on GPU resources
# import gc; gc.collect(); torch.cuda.empty_cache(); del model

# 2. Align whisper output
model_a, metadata = wshisperx.load_align_model(language_code=result["language"], device=device)
result = wshisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

print(result["segments"]) # after alignment

# delete model if low on GPU resources
# import gc; gc.collect(); torch.cuda.empty_cache(); del model_a

# 3. Assign speaker labels
diarize_model = wshisperx.DiarizationPipeline(use_auth_token="", device=device)

# add min/max number of speakers if known
diarize_segments = diarize_model(audio)
# diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)

result = wshisperx.assign_word_speakers(diarize_segments, result)
print(diarize_segments)
print(result["segments"]) # segments are now assigned speaker IDs