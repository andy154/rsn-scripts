import whisperx
import requests

def download_file(url, local_filename):
    response = requests.get(url, stream=True)
    with open(local_filename, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    return local_filename

device = "cuda" 
audio_file = "audio.mp3"
download_file("https://amocrm.mango-office.ru/calls/recording/download/11020017/MToxMDE1MDk4NDoxODk2MDE2NzY2MTow/NDAzNjI3OTY1", audio_file)
batch_size = 16 # reduce if low on GPU mem
compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)

model = whisperx.load_model("large-v3", device, language="ru", compute_type=compute_type)

audio = whisperx.load_audio(audio_file)
result = model.transcribe(audio, batch_size=batch_size)
text = ""

for segment in result["segments"]:
    text += segment["text"]

print(text)