import ollama

response = ollama.chat(
    model='mistral',  # или другая модель, например 'gemma:2b'
    messages=[
        {'role': 'user', 'content': 'Привет! Кто ты такой?'}
    ]
)

print(response['message']['content'])