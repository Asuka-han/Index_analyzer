FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-ui.txt /app/requirements-ui.txt
RUN pip install --no-cache-dir -r requirements-ui.txt

COPY src /app/src
COPY ui /app/ui
COPY scripts /app/scripts
COPY data /app/data
COPY result /app/result
COPY 高频宏观数据指标库.xlsx /app/高频宏观数据指标库.xlsx

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "ui/industry_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
