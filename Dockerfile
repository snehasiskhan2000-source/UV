FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install ffmpeg and aria2c to handle m3u8 streams safely
RUN apt-get update && \
    apt-get install -y ffmpeg aria2 && \
    rm -rf /var/lib/apt/lists/*

# Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
