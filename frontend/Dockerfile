FROM node:20-alpine AS build
WORKDIR /app

# O build do Vite/Tailwind precisa das devDependencies.
# Esta versao e resistente a ambientes Windows porque remove qualquer
# node_modules/dist copiado do host antes de instalar dentro do Linux.
ENV NODE_ENV=development
ENV NPM_CONFIG_PRODUCTION=false
ENV CI=true

COPY . .
RUN rm -rf node_modules dist \
    && npm config set production false \
    && npm ci --include=dev --no-audit --no-fund \
    && node -e "require.resolve('vite/package.json'); console.log('vite OK')" \
    && npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
