FROM node:20-alpine AS build
WORKDIR /app

# O build do Vite/Tailwind depende de pacotes em devDependencies.
# Em alguns ambientes o Docker recebe NODE_ENV=production/NPM_CONFIG_PRODUCTION=true,
# o que faz o npm ci pular devDependencies e deixa o binario vite indisponivel
# no passo `npm run build` (erro 127). Forcamos a inclusao aqui.
ENV NODE_ENV=development
ENV NPM_CONFIG_PRODUCTION=false

COPY package*.json ./
RUN npm ci --include=dev --no-audit --no-fund

COPY . .
RUN test -x node_modules/.bin/vite && npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
