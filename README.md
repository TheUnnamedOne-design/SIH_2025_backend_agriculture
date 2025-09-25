```
agricultural-ai-assistant/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api.py
│   │   └── health.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_service.py
│   │   ├── soil_service.py
│   │   ├── api_service.py
│   │   ├── rag_service.py
│   │   ├── location_service.py
│   │   └── embedding_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── data_models.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   └── validators.py
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── templates/
│       ├── base.html
│       ├── index.html
│       └── results.html
├── data/
│   ├── embeddings/
│   ├── pdfs/
│   └── soil_data/
├── tests/
│   ├── __init__.py
│   ├── test_services.py
│   └── conftest.py
├── requirements.txt
├── .env
├── .gitignore
└── run.py
```
