FROM node:20-alpine AS build
WORKDIR /app

# O Vite/Tailwind rodam apenas no stage de build. Mantemos NODE_ENV
# em development para impedir que o npm omita dependencias necessarias.
ENV NODE_ENV=development
ENV NPM_CONFIG_PRODUCTION=false
ENV NPM_CONFIG_OMIT=""
ENV CI=true

COPY package.json package-lock.json ./
RUN npm ci --include=dev --no-audit --no-fund
RUN node -e "require.resolve('vite/package.json'); console.log('vite OK')"

COPY . .
RUN rm -rf dist && npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
