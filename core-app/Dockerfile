FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install dependencies needed by Playwright/Chromium (for PDF rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
	ca-certificates \
	wget \
	fonts-liberation \
	libnss3 \
	libglib2.0-0 \
	libatk1.0-0 \
	libatk-bridge2.0-0 \
	libcups2 \
	libxcomposite1 \
	libxdamage1 \
	libxrandr2 \
	libgbm1 \
	libasound2 \
	libxss1 \
	libgtk-3-0 \
	libpangocairo-1.0-0 \
	libdbus-1-3 \
	libexpat1 \
	libfontconfig1 \
	libx11-6 \
	libx11-xcb1 \
	libxext6 \
	libxfixes3 \
	libxcb1 \
	libxkbcommon0 \
	libxtst6 \
	libxshmfence1 \
	libnspr4 \
 && rm -rf /var/lib/apt/lists/*

# System packages required by WeasyPrint (cairo, pango, gdk-pixbuf etc.)
# Use package names that are available across Debian releases: libgdk-pixbuf-xlib
# is provided in newer suites, and libffi-dev is a safer dependency provider.
RUN apt-get update && apt-get install -y --no-install-recommends \
	libcairo2 \
	libpango-1.0-0 \
	libgdk-pixbuf-xlib-2.0-0 \
	libffi-dev \
	libxml2 \
	libxslt1.1 \
	&& rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN python3 -m playwright install chromium

EXPOSE 5000
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec gunicorn app:app -w $(( $(nproc) * 2 + 1 )) --threads=4 --bind=0.0.0.0:5000 --timeout=30 --log-level=info"]
