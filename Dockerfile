FROM python:3.11-slim

WORKDIR /app

COPY headline_body_checker_nordot_app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY headline_body_checker_nordot_app/ ./headline_body_checker_nordot_app/

EXPOSE 8501

CMD ["streamlit", "run", "headline_body_checker_nordot_app/main_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
