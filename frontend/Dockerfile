# frontend/Dockerfile
FROM node:16-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build

# Use a simple static server (like serve) to serve the build
RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "8080"]
