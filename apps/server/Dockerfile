FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
ENV QLOO_API_KEY=""
ENV QLOO_BASE_URL="https://hackathon.api.qloo.com"
ENV CORS_ALLOW_ALL="true"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]