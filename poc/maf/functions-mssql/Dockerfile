FROM mcr.azure.cn/azure-functions/python:4-python3.11
COPY requirements.txt /tmp/poc-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/poc-requirements.txt
COPY host.json function_app.py /home/site/wwwroot/
ENV AzureWebJobsScriptRoot=/home/site/wwwroot
