# MiroEdo backend — Python 3.11 (required by camel-oasis 0.2.x).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for PyMuPDF and OASIS native wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps in a single pip invocation so the resolver finds a
# consistent solution across base + simulation extras.
COPY requirements.txt requirements-simulation.txt ./
RUN pip install -r requirements.txt -r requirements-simulation.txt

# App code
COPY app ./app
COPY tests ./tests
COPY pyproject.toml ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
