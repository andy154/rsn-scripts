from supabase import create_client, Client

SUPABASE_URL = "https://ovuonhjvnbvbotxmaamq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92dW9uaGp2bmJ2Ym90eG1hYW1xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIyODY5ODcsImV4cCI6MjA1Nzg2Mjk4N30.54pYR5LrPH3YGHU81jAO3dnVhu3IhHgcaBHqOhcoksM"

# Создаем клиент Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Успешное подключение к Supabase!")

data = {
    "company_id": 123123123,
    "call_id": 456456456,
    "text": "qweqweqwe"
}

response = supabase.table("calls").insert(data).execute()
print(response)