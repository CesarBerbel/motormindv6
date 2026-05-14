FROM node:20-bookworm-slim AS build
WORKDIR /app

# Build deterministico para producao. O Docker instala somente dependencies
# porque vite/tailwind/postcss ja estao em dependencies; vitest/jsdom ficam fora.
ENV CI=true \
    NODE_ENV=production \
    NPM_CONFIG_AUDIT=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_PROGRESS=false \
    NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_REGISTRY=https://registry.npmjs.org/

COPY . .
RUN rm -rf node_modules dist .vite

# Nao instala devDependencies no build Docker. Isso evita downloads lentos de
# jsdom/vitest e remove os avisos de whatwg-encoding/lodash.isequal.
RUN npm ci --omit=dev --no-audit --no-fund --loglevel=notice
RUN node -e "require.resolve('vite/package.json'); console.log('vite OK')"
RUN node ./node_modules/vite/bin/vite.js build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
