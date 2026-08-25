function required(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const config = Object.freeze({
  port: Number(process.env.WS_PORT ?? 8081),
  redisUrl: required("REDIS_URL"),
  jwtSigningKey: required("JWT_SIGNING_KEY"),
});
