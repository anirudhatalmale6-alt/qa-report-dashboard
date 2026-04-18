FROM node:18-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci --production

# Copy application code
COPY server.js ./
COPY public/ ./public/

# Copy ai-tools if it exists (optional)
COPY ai-tool[s]/ ./ai-tools/

# Create reports directory (will be overridden by volume mount)
RUN mkdir -p /app/reports

# Expose the dashboard port
EXPOSE 3000

# Start the server
CMD ["node", "server.js"]
