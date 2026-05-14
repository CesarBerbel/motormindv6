FROM node:20-alpine AS build
WORKDIR /app

# O build do Vite/Tailwind depende de pacotes em devDependencies.
# Mantemos NODE_ENV como development apenas no stage de build para garantir
# que vite, tailwind e postcss sejam instalados mesmo quando o ambiente Docker
# do host define producao por padrao.
ENV NODE_ENV=development
ENV NPM_CONFIG_PRODUCTION=false
ENV CI=true

COPY package*.json ./
RUN npm ci --include=dev --no-audit --no-fund

# Importante: frontend/.dockerignore exclui node_modules/dist do host.
# Sem isso, o COPY abaixo pode sobrescrever os node_modules Linux gerados
# pelo npm ci com node_modules do Windows, quebrando o binario do Vite.
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
