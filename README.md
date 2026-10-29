# NHS CareFinder AI — runnable MVP

🚀 **[Open Live Demo](https://nhs-carefinder-ai-web.onrender.com/)**

Patient-facing NHS service navigation demo. It is **not a diagnostic or booking product** and it does not indicate provider capacity.

## Includes
- React/Vite responsive frontend
- FastAPI backend
- DoHS API v3 adapter configured for NHS `api.service.nhs.uk/service-search-api`
- Location/postcode search and distance ranking (postcode geocoding is a separate adapter; demo coordinates used if no configured geocoder)
- Local Ollama-powered chatbot (no paid AI API key required); conservative safety prompt and safe fallback
- MCP server tool for service discovery
- Pytest tests, Bandit/Pip-audit/ruff workflow, Locust load test
- Docker Compose and GitHub Actions

## Start
```bash
cp .env.example .env
docker compose up --build
```
Frontend: http://localhost:5173  
API docs: http://localhost:8000/docs  
API health: http://localhost:8000/health

Without `NHS_API_KEY`, API uses clearly labeled synthetic demo fixtures. Obtain an API subscription key and review the official v3 contract before enabling live mode. The NHS DoHS API v3 is active; v1/v2 were scheduled for retirement on 2 February 2026. References:
- https://digital.nhs.uk/developer/api-catalogue/directory-of-healthcare-services
- https://digital.nhs.uk/developer/api-catalogue/directory-of-healthcare-services/version-3
- https://digital.nhs.uk/developer/guides-and-documentation/building-healthcare-software/organisations-and-services

## AI limitations
The chatbot now calls a local Ollama model (`llama3.2:1b`). This is a general language model, not a clinically validated system and not connected to a verified NHS knowledge base. It may make mistakes; it does not provide medical diagnosis, live service availability, appointment booking, or sourced clinical guidance. Before public use, add retrieval from reviewed official NHS sources with source citations, test safety behaviour, and obtain appropriate clinical and information-governance review. Do not send identifiable health information.

If the chatbot cannot connect to Ollama, check `docker compose ps` and `docker compose logs --tail=100 ollama api`. Confirm the model pull completed and `.env` contains `OLLAMA_URL=http://ollama:11434` and `OLLAMA_MODEL=llama3.2:1b`.

## Production caveats
The NHS API adapter is a useful integration starting point but the returned fields and query filters must be validated against your API key's official OpenAPI contract and sandbox. Distance sorting requires reliable geocodes; the directory's geospatial fields may be absent. Do not scrape NHS pages or infer appointment availability. Real appointment/referral integrations need separate onboarding and approvals.

Before public clinical deployment, determine medical-device status and clinical safety obligations; perform a DPIA, NHS assurance, DCB0129/0160 assessment where applicable, penetration testing, accessibility checks, and clinical content review. Do not send symptoms or identifiable health data to an unapproved LLM. Emergency: 999 for life-threatening emergencies; NHS 111 for urgent advice in England.
