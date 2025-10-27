FROM python:3-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy the requirements file
COPY app/requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run your application
CMD ["python", "main.py"]
