# Text Translation Service

FastAPI service for translating SRT subtitle files using Google GenAI's Gemini 2.5 Pro model.

## Features

- **SRT Format Support**: Preserves timestamps and structure
- **Enhanced Translation**: Multi-step reasoning with extended thinking for subtitle-optimized translations
- **Localization Support**: Optional country/region parameter for cultural adaptation
- **Contextual Chunking**: Groups consecutive entries for better translation context and quality
- **Concurrent Processing**: Handles multiple chunks simultaneously for speed
- **Multiple Requests**: Async architecture supports concurrent client requests
- **API Key Authentication**: Optional authentication layer
- **Google GenAI Integration**: Uses Gemini 2.5 Pro with extended thinking
- **Auto Documentation**: Interactive API docs at `/docs`

## Project Structure

```
text-translation-service/
├── main.py                   # FastAPI server
├── srt_parser.py            # SRT parsing/reconstruction
├── google_genai_client.py   # Google GenAI API client
├── pyproject.toml           # Dependencies
├── .env.example             # Environment template
├── .gitignore               # Git exclusions
└── README.md                # This file
```

## Setup

1. **Clone and install dependencies:**

   ```bash
   pip install -e .
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenRouter API key
   ```

3. **Get Google GenAI API key:**
   - Visit <https://aistudio.google.com/apikey>
   - Create/sign in to Google account and generate API key
   - Add to `.env` as `GOOGLE_API_KEY`

4. **Optional: Enable authentication:**
   - Set `API_KEY` in `.env` to enable X-API-Key header validation
   - Leave unset to disable authentication

## Running

**Development mode:**

```bash
uvicorn main:app --reload
```

**Production mode:**

```bash
python main.py
```

Server runs at `http://localhost:8000`

## API Usage

### Health Check

```bash
curl http://localhost:8000/
```

### Translate SRT File

**Without authentication:**

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "srt_content": "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n2\n00:00:05,000 --> 00:00:08,000\nHow are you?",
    "target_language": "Spanish"
  }'
```

**With authentication:**

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "srt_content": "...",
    "target_language": "French"
  }'
```

**With localization:**

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "srt_content": "...",
    "target_language": "Portuguese",
    "country": "Brazil"
  }'
```

**Request parameters:**

- `srt_content` (required): SRT file content as string
- `target_language` (required): Target language (e.g., "Spanish", "French", "Japanese")
- `source_language` (optional): Source language hint
- `country` (optional): Target country/region for localization (e.g., "Brazil", "Spain", "Mexico")
- `model` (optional): Google GenAI model override (default: gemini-2.5-pro)
- `chunk_size` (optional): Number of consecutive entries to translate together (default: 8, range: 1-20)

**Translation process:**

The service groups consecutive subtitle entries (default: 8) for better context, then uses a 6-step reasoning process with extended thinking:
1. Context analysis (dialogue flow, text type, domain, cultural elements)
2. Translation challenges (idioms, cultural adaptation, consistency across entries)
3. Subtitle constraints (conciseness, line breaks, reading speed)
4. Initial translation (considering dialogue flow between entries)
5. Self-critique (accuracy, fluency, style, timing, cultural fit, contextual coherence)
6. Final improved translation

**Benefits of chunking:**
- Better context: Translator sees dialogue flow and narrative continuity
- Improved consistency: Character names, terms, and tone maintained across entries
- Natural dialogue: Responses/reactions translated with awareness of preceding lines

**Response:**

```json
{
  "translated_srt": "1\n00:00:01,000 --> 00:00:04,000\nHola mundo\n\n2\n00:00:05,000 --> 00:00:08,000\n¿Cómo estás?",
  "entry_count": 2
}
```

## Interactive Documentation

Visit `http://localhost:8000/docs` for Swagger UI with interactive API testing.

## Error Handling

- **400 Bad Request**: Invalid SRT format
- **401 Unauthorized**: Missing/invalid API key (if auth enabled)
- **502 Bad Gateway**: Google GenAI API error
- **500 Internal Server Error**: Unexpected error

## Development

GitHub Issue: [#1](https://github.com/syz51/text-translation-service/issues/1)

## License

MIT
