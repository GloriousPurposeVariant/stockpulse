FROM node:22-slim

# Set before npm ci: with this in the environment, npm skips devDependencies
# on its own, and Fastify and friends check it at runtime for their production
# code paths.
ENV NODE_ENV=production

WORKDIR /app

# Both files, then install, then the source. Editing server.js leaves the
# npm layer cached; changing a dependency is the only thing that busts it.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

# node:22-slim ships a `node` user at uid 1000 already - no need to create one.
USER node

EXPOSE 8081

# No --env-file. A container's environment comes from compose, which is
# exactly what your `start` script was written for.
CMD ["node", "src/server.js"]
