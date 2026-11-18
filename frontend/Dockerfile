FROM node:22-bookworm-slim AS build
WORKDIR /ui
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html