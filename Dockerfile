FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["sh", "-c", "python refresh_scheduler.py & exec python -m streamlit run asgi_app.py --server.port ${PORT:-8000} --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false"]
