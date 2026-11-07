"""Fabricated organizer-shaped fixture; no real customer data."""


def dataset_payload():
    records = []
    for index in range(65):
        language = "RU" if index < 35 else "KZ" if index < 50 else "EN"
        call = index >= 60
        texts = {
            "RU": ["Здравствуйте. Сколько стоит карта?", "Здравствуйте! Я Анна. Тариф уточню."],
            "KZ": ["Сәлеметсіз бе. Карта бағасы қандай?", "Сәлеметсіз бе! Мен Айданамын."],
            "EN": ["Hello. What does a card cost?", "Hello! I am Alex."],
        }[language]
        records.append(
            {
                "conversation_id": f"synthetic-{index}",
                "language": language,
                "channel": "voice call" if call else "agent chat",
                "audio_url": "https://audio.example.invalid/synthetic.wav" if call else None,
                "transcript": [
                    {
                        "timestamp": "2026-11-07T14:30:00+05:00" if call else "00:00",
                        "speaker": "system",
                        "text": "Synthetic context",
                    },
                    {
                        "timestamp": "2026-11-07T14:30:01+05:00" if call else "00:01",
                        "speaker": "bot",
                        "text": "Synthetic bot",
                    },
                    {
                        "timestamp": "2026-11-07T14:30:02+05:00" if call else "00:02",
                        "speaker": "client",
                        "text": texts[0],
                    },
                    {
                        "timestamp": "2026-11-07T14:30:03+05:00" if call else "00:03",
                        "speaker": "operator",
                        "text": texts[1],
                    },
                ],
            }
        )
    return {"isSuccess": True, "data": {"records": records, "total_records": 65}}
