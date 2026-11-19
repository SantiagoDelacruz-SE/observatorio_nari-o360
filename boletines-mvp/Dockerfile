FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev --no-audit --no-fund
COPY server.js ./
COPY public ./public
ENV NODE_ENV=production
EXPOSE 10000
CMD ["node","server.js"]
