FROM node:20-alpine AS build
WORKDIR /app

# Copia primeiro todo o frontend e remove qualquer artefato vindo do host
# antes da instalacao. Isso evita sobrescrever node_modules Linux com
# node_modules do Windows no passo COPY.
ENV CI=true

COPY . .
RUN rm -rf node_modules dist .vite

# Instala as dependencias de build depois do COPY para garantir que vite
# exista no ambiente Linux da imagem final de build.
RUN npm ci --include=dev --no-audit --no-fund
RUN node -e "require.resolve('vite/package.json'); console.log('vite OK')"

# Chama o Vite diretamente para nao depender do PATH do npm script.
RUN node ./node_modules/vite/bin/vite.js build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
