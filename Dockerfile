FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY agent.py api.py app.py approvals.py auth.py config.py init_demo.py llm_client.py memory.py mock_llm.py rag.py security.py storage.py tools.py ui.html ./
RUN useradd --create-home lab && mkdir -p /app/data && chown -R lab:lab /app
USER lab
EXPOSE 8000
CMD ["sh", "-c", "python init_demo.py && uvicorn api:create_app --factory --host 0.0.0.0 --port 8000 --no-access-log"]

