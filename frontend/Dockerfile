# =============================================================================
# DuckPools Coinflip - Frontend Dockerfile
# =============================================================================
#
# Multi-stage build for React + Vite frontend
# - development: Hot-reload enabled, dev server runs on port 3000
# - production: Optimized static build, serves with nginx
#
# Usage:
#   docker build -t duckpools-frontend --target development .
#   docker build -t duckpools-frontend:prod --target production .
# =============================================================================

# =============================================================================
# Development Stage - Node Runtime with Dev Server
# =============================================================================
FROM node:20-alpine as development

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Expose ports
EXPOSE 3000 24678

# Environment variables for hot-reload
ENV CHOKIDAR_USEPOLLING=true \
    VITE_API_ENDPOINT=http://localhost:8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

# Run Vite dev server
CMD ["npm", "run", "dev"]

# =============================================================================
# Build Stage - Create Production Build
# =============================================================================
FROM node:20-alpine as build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Build production bundle
RUN npm run build

# =============================================================================
# Production Stage - Serve Static Files
# =============================================================================
FROM node:20-alpine as production

# Set working directory
WORKDIR /app

# Copy package files (for preview server)
COPY package*.json ./

# Install only production dependencies
RUN npm ci --only=production

# Copy built artifacts from build stage
COPY --from=build /app/dist ./dist

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Serve with Vite preview server (or could use nginx)
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "80"]
