# Compile the SPA, then throw the toolchain away. Node is not in the final
# image; only the static files it produced.
FROM node:24-slim AS build
WORKDIR /app
# Lockfile first, so editing a component does not reinstall 300 packages.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
# The packaged default site would otherwise take precedence over ours.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
# Straight into the directory `location /` already points at.
COPY --from=build /app/dist /usr/share/nginx/html
