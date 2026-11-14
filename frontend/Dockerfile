# Etapa 1: Node compila o React (TypeScript → JS/HTML/CSS em /app/dist)
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Etapa 2: só o resultado vai para o Nginx (o Node não fica na imagem final)
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
